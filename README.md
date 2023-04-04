# web_scraper
Python script for a web scraper using Selenium, Beautiful Soup, and SQLAlchemy.
It is designed to scrape the specified initial URL and follow links up to a specified maximum depth while storing the scraped data in an SQLite database.
It also supports resuming the scraping process from where it left off and utilizes multi-threading for improved performance.

Here is a breakdown of the code:
1. Importing required libraries and modules.
2. Setting the path to the chromedriver.exe file, configuring the logging module, and creating a lock object for synchronized access to the log file.
3. Defining a custom JSON encoder class SetEncoder to handle encoding of sets.
4. Defining the create_database function to create an SQLite database and the corresponding ORM session.
5. Defining the Page ORM class to map the 'pages' table in the SQLite database.
6. Defining the Scraper class to handle the scraping process:
  - Initialization: setting up initial configurations, including Chrome WebDriver options.
  - start_scraping: starting the scraping process, either by resuming from the last scraped position or starting anew.
  - resume_scraping: resuming the scraping process from the last scraped URL.
  - scrape: the main scraping function that handles visiting URLs and extracting the page's title and links.
  - get_links: extracting all the links from a given BeautifulSoup object.
  - get_link: processing a single link, checking if it should be followed, and adding it to the database if necessary.
  - save_to_db: putting the scraped data into the queue for insertion into the database.
  - run_db_inserts: handling the insertion of the scraped data into the database.
  - cleanup: cleaning up resources such as the WebDriver and stopping the database insertion thread.
7. The main function:
  - Parsing command-line arguments for the initial URL, maximum depth, SQLite database file, and the maximum number of threads.
  - Creating an instance of the Scraper class with the specified arguments.
  - Starting the scraping process and performing cleanup afterward.

To run the script, you would use the following command:
python <script_name>.py <initial_url> <max_depth> [--db_file <database_file>] [--max_threads <number_of_threads>]

Replace <script_name> with the name of the Python file,
<initial_url> with the URL you want to start scraping from,
<max_depth> with the maximum depth of links you want to follow,
and optionally provide the --db_file and --max_threads flags to specify the database file and the maximum number of threads to use.

In addition to the main Python script there are two additional files:
1. scraper_requirements.txt
2. Dockerfile.
These files are used to create a Docker container to run the web scraper.

scraper_requirements.txt lists the required Python packages for the web scraper to function properly.
This includes Beautiful Soup, Selenium, WebDriver Manager, LXML, and SQLAlchemy.
These packages will be installed within the Docker container when it is built.

Dockerfile is a script that contains instructions for building a Docker container.
Here's a breakdown of the steps involved in this file:
1. Specify the base image as python:3.9-slim-buster, which is a slim version of Python 3.9 based on the Debian Buster distribution.
2. Set the working directory of the container to /app.
3. Update and install necessary dependencies such as curl, gnupg, unzip, build-essential, libgconf-2-4, and wget.
4. Download and install Google Chrome browser and Chromedriver for Linux.
5. Set the environment variable for Chromedriver.
6. Set the container name as web_scraper.
7. Copy the current directory contents (including the main Python script and requirements file) into the container at /app.
8. Install the required Python packages specified in scraper_requirements.txt.
9. Set the entry point for the container to run the scraper.py script and display the help message by default.
10. Clean up after the installation.
11. Create a volume for the SQLite database to persist data between container runs.

When you build and run the Docker container, it will create an isolated environment with all the necessary dependencies to execute the web scraper.
The advantage of using a Docker container is that you can easily deploy and run the scraper on any machine that supports Docker,
without worrying about dependency conflicts or other issues related to the host machine's environment.