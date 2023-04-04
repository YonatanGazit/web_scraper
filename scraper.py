import argparse
import concurrent.futures
import json
import logging
import queue
import threading
import codecs
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base

# Set the path to the chromedriver.exe file
CHROME_DRIVER_PATH = "/usr/local/bin/chromedriver"

# Configure the logging module
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scraper_log.txt", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# Create a lock object to synchronize access to the log file
log_lock = threading.Lock()

# Custom JSON encoder class
class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return super().default(obj)

# Create the engine and sessionmaker objects
engine = None
Session = None

def create_database(db_file):
    global engine, Session
    engine = create_engine(f"sqlite:///{db_file}", connect_args={'check_same_thread': False})
    Session = sessionmaker(bind=engine)
    # Create the pages table if it does not exist
    Base.metadata.create_all(engine)

# Create the declarative base for defining the ORM classes
Base = declarative_base()

# Define the ORM class for the 'pages' table
class Page(Base):
    __tablename__ = 'pages'
    url = Column(String, primary_key=True)
    source_url = Column(String)
    depth = Column(Integer)
    title = Column(String)
    links = Column(Text)

    def __init__(self, url, source_url, depth, title, links):
        self.url = url
        self.source_url = source_url
        self.depth = depth
        self.title = title
        self.links = links

    def __repr__(self):
        return f"<Page(url='{self.url}', depth={self.depth})>"

class Scraper:
    def __init__(self, initial_url, max_depth, db_file=None, max_threads=10):
        self.initial_url = initial_url
        self.max_depth = max_depth
        self.db_file = db_file or 'scraper.db'
        self.db_insert_queue = queue.Queue()
        self.max_threads = max_threads
        self.visited_urls = set()
        self.connection_pool = queue.Queue(maxsize=max_threads)

        # Configure the Chrome driver
        CHROME_OPTIONS = webdriver.ChromeOptions()
        CHROME_OPTIONS.add_argument("--headless")
        CHROME_OPTIONS.add_argument("--disable-dev-shm-usage")
        CHROME_OPTIONS.add_argument("--no-sandbox")
        CHROME_OPTIONS.add_argument("--disable-browser-side-navigation")
        CHROME_OPTIONS.add_argument("--disable-infobars")
        CHROME_OPTIONS.add_argument("--disable-extensions")

        # Set up the Selenium web driver
        self.service = Service(CHROME_DRIVER_PATH)
        self.service.start()
        self.driver = webdriver.Remote(
            self.service.service_url,
            desired_capabilities=CHROME_OPTIONS.to_capabilities()
        )

        create_database(self.db_file)

    def start_scraping(self):
        # Check if the database already has some URLs scraped
        with Session() as session:
            count = session.query(Page).filter_by(url=self.initial_url).count()

        if count > 0:
            logging.info(
                f"Resuming scraping from last position ({count} pages in database) for URL: {self.initial_url}")
            self.resume_scraping()
        else:
           logging.info(
                f"Start Scraping from {self.initial_url} with max depth of {self.max_depth}")
           self.scrape(self.initial_url, depth=0)

        # Start the thread for inserting scraped data into the database
        db_insert_thread = threading.Thread(target=self.run_db_inserts)
        db_insert_thread.start()

    def resume_scraping(self):
        # Find the last page scraped and its depth for the initial URL
        with Session() as session:
            last_page = session.query(Page).filter_by(url=self.initial_url).order_by(Page.depth.desc()).first()

        if last_page is None:
            logging.error(f"No data found in database for URL: {self.initial_url}")
            return

        last_url, last_depth = last_page.url, last_page.depth

        # If the last depth is greater than or equal to the new max depth, then we are done
        if last_depth >= self.max_depth:
            logging.info(f"All data has been scraped for URL: {self.initial_url}")
            return

        # Skip URLs until the last URL is reached
        while self.url_queue.qsize() > 0:
            url, depth = self.url_queue.get()
            if url == last_url:
                self.url_queue.put((url, depth))
                break

        self.visited_urls.add(last_url)

        with log_lock:
            logging.info(f"Resuming scraping from {last_url}, depth={last_depth}")

        # Continue scraping from the last page scraped
        self.scrape(last_url, last_depth)

    def scrape(self, url, depth):
        if depth > self.max_depth:
            return

        if url in self.visited_urls:
            return
        self.visited_urls.add(url)

        try:
            self.driver.get(url)
        except Exception as e:
            with log_lock:
                logging.error(f"Error scraping {url}: {e}")
            return

        soup = BeautifulSoup(self.driver.page_source, "lxml")
        title = soup.title.string.strip()

        links = self.get_links(soup, url)

        result = (url, self.driver.current_url, depth, title, links)
        self.save_to_db(result)

        with log_lock:
            logging.info(
                f"Scraped {url}, depth={depth}, title='{title}'")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = [executor.submit(
                self.scrape, link, depth + 1) for link in links if depth + 1 <= self.max_depth]
            concurrent.futures.wait(futures)

    def get_links(self, soup, url):
        links = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = []
            for link in soup.find_all("a"):
                href = link.get("href")
                if href:
                    # If the link is a relative URL, add the initial URL's domain to the beginning
                    if href.startswith("/"):
                        href = urljoin(self.initial_url, href)
                    # If the link is missing the initial URL's domain, add it to the beginning
                    elif not href.startswith("http"):
                        href = urljoin(self.initial_url, href)
                    future = executor.submit(self.get_link, href)
                    futures.append(future)
            for future in concurrent.futures.as_completed(futures):
                links += future.result()
        return links

    def get_link(self, href):
        links = []
        try:
            parsed_url = urlparse(href)
            # Only follow links to the same domain
            if parsed_url.netloc == urlparse(self.initial_url).netloc:
                with Session() as session:
                    # Check if the URL is already in the database
                    page = session.query(Page).filter_by(url=href).first()
                    if page is None:
                        # If the URL is not in the database, add it to the URL queue
                        links.append(href)
                        page = Page(url=href, source_url=self.driver.current_url, depth=0, title="", links=set())
                        session.add(page)
                        session.commit()
                    elif page.depth < self.max_depth:
                        # If the URL is in the database and its depth is less than the max depth, add it to the URL queue
                        links.append(href)
                        page.depth += 1
                        session.merge(page)
                        session.commit()
        except Exception as e:
            with log_lock:
                logging.error(f"Error parsing URL {href}: {e}")
        return links

    def save_to_db(self, result):
        self.db_insert_queue.put(result)

    def run_db_inserts(self):
        with Session() as session:
            while True:
                try:
                    result = self.db_insert_queue.get()
                    if result is None:
                        break
                    url, source_url, depth, title, links = result
    
                    # Encode the title string using UTF-8 encoding
                    title_encoded = codecs.encode(title, 'utf-8')
    
                    # Check if links are already serialized to JSON
                    if not isinstance(links, str):
                        links = json.dumps(links, cls=SetEncoder)
    
                    page = Page(
                        url=url,
                        source_url=source_url,
                        depth=depth,
                        title=title_encoded,
                        links=links
                    )
                    session.merge(page)
                    session.commit()
                except Exception as e:
                    with log_lock:
                        logging.error(f"Error saving {url} to database: {e}")
                    session.rollback()

    def cleanup(self):
        self.driver.quit()
        self.service.stop()

        # Insert None into the queue to signal the database insertion thread to exit
        self.db_insert_queue.put(None)
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Web scraper")
    parser.add_argument("initial_url", help="The initial URL to start scraping from")
    parser.add_argument("max_depth", type=int, help="The maximum depth of links to follow")
    parser.add_argument("--db_file", help="Use the --db_file flag to set the SQLite database file. If not given default is scraper.db")
    parser.add_argument("--max_threads", type=int, default=10, help="Use the --max_threads flag to set the maximum number of threads. If not given default is 10")
    
    args = parser.parse_args()

    scraper = Scraper(args.initial_url, args.max_depth, args.db_file, args.max_threads)
    scraper.start_scraping()
    scraper.cleanup()


if __name__ == "__main__":
    main()
