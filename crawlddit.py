#!/usr/bin/python3


import os
import re
from argparse import ArgumentParser
from contextlib import suppress
from urllib.request import urlopen
from urllib.request import urlretrieve
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException
from utils.debugtools import get_all_domains
from utils.debugtools import print_all_domains
from utils.debugtools import count_downloadable_images
from utils.politeness import get_politeness_factor
from utils.consoleaccessories import Colors
from collections import deque
from time import sleep


FILE_FORMATS = ['.jpg', '.jpeg', '.png', '.gif', '.webm']
DOMAINS = ['reddit', 'imgur', 'gfycat', 'tumblr', 'blogspot']


class DomainMissingException(Exception):
    pass


def parse_arguments():
    """
    Parse input arguments of the program. Two positional arguments are
    mandatory: 'URL' and destination 'directory'. 'verbose' is optional.
    Example:

    crawlddit.py -v https://www.reddit.com/r/MemeEconomy/ ./dank_memes

    For more information type:

    crawlddit.py --help
    """
    parser = ArgumentParser(description='reddit /r downloader')

    parser.add_argument('-v', '--verbose',
                        help='display download progress and information',
                        action='store_true')
    parser.add_argument('-p', help='crawl P number of pages', type=int)
    parser.add_argument('URL', help='source link')
    parser.add_argument('directory', help='destination directory')

    args = parser.parse_args()

    return (args.verbose, args.p, args.URL, args.directory)


def make_soup(url, parser='lxml', selenium=False):
    """
    Return a soup object. Default parser is lxml. Requests are made by
    default using url.request library.
    """
    if selenium:
        driver = webdriver.PhantomJS()
        driver.get(url)
        html = driver.page_source
        driver.close()
        return BeautifulSoup(html, parser)
    return BeautifulSoup(urlopen(url).read(), parser)


def make_beautiful_soup(url, driver, parser='lxml'):
    """
    Get soup object from url using selenium driver. If request is
    redirected, then confirm redirect dialog.
    """
    driver.get(url)

    with suppress(NoSuchElementException):
        submit_exists = driver.find_element_by_xpath(
            "//button[@type='submit'][@value='yes']"
        )

        confirm_redirect_dialog(driver)

    return BeautifulSoup(driver.page_source, parser)


def confirm_redirect_dialog(driver):
    """
    If redirection dialog pops up, click confirm/continue button.
    """
    button = driver.find_element_by_xpath(
        "//button[@type='submit' and @value='yes']"
    )
    driver.execute_script("arguments[0].click();", button)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//span[@class='next-button']")
            )
        )
    except TimeoutException as e:
        driver.save_screenshot('screenshot.png')
        print('Loading taking too much time.\n', e)


def get_all_posts(url, pages):
    """
    Crawl links of all posts, or posts from P number of pages. If P
    i.e. 'pages' is 0, then crawl all pages.
    """
    driver = webdriver.PhantomJS()

    images = deque()
    crawl = True
    crawl_time = get_politeness_factor('reddit')
    page = 1 if pages else 0

    while (page <= pages) and crawl:
        soup = make_beautiful_soup(url, driver)
        pictures, next_page = get_files_from_a_page(soup, url)

        images.extend(pictures)
        url = next_page

        if pages: page += 1
        if not next_page: crawl = False

        sleep(crawl_time)

    driver.close()
    return images


def get_files_from_a_page(soup, url=None):
    """
    Get links and other information to all files from a single page.
    Return link for next page if it exists.
    """
    things = soup.find_all('div', attrs={'class' : re.compile(r'\sthing\sid-t3.+')})
    images = deque({
            'url' : get_post_url(div),
            'image' : get_image(div),
            'domain' : get_post_domain(div),
            'post_title' : get_post_title(div),
            'posted_on' : get_post_timestamp(div),
            'link_to_comments' : get_link_to_comments(div),
            'on_page' : url,
            'html_status_token' : 0,
        } for div in things
    )

    next_page_span = soup.find('span', attrs={'class' : 'next-button'})
    next_page = next_page_span.a['href'] if next_page_span else None

    return (images, next_page)


def get_image(div):
    """
    Get image url and image filename.
    """
    url = get_post_url(div)
    if known_file_format(url):
        return image_dictionary(url, get_image_filename(url))
    image_url = get_image_link_from_allowed_domain(url, known_domain(url))
    filename = get_image_filename(image_url) if image_url else None
    return image_dictionary(image_url, filename)


def get_image_link_from_allowed_domain(url, domain):
    """
    Use correct domain parser.
    """
    if domain == 'reddit':
        return None
    elif domain == 'imgur':
        return None
    elif domain == 'gfycat':
        return parse_gfycat(url)
    elif domain == 'tumblr':
        return None
    elif domain == 'blogspot':
        return None
    else:
        return None
    # ugly dangling else
    # raise DomainMissingException('Unknown domain, missing parsing tools.')


def parse_gfycat(url):
    """
    Get direct link for post image/video from gfycat.
    """
    soup = make_soup(url)
    source = soup.find('source', attrs={'id' : 'webmSource'})
    return source['src'] if source else None


def known_domain(url):
    """
    Check if the domain is in the list of known/allowed domains.
    """
    for domain in DOMAINS:
        if domain in url:
            return domain
    return None


def get_image_filename(url):
    """
    Get image file name from its url.
    """
    candidate = url.split('/')[-1]
    extension = known_file_format(url)
    pattern = ''.join(['.+\\', extension])
    return re.match(pattern, candidate).group(0)


def image_dictionary(url, filename):
    """
    Returns a dictionary with image url and corresponding filename.
    """
    return { 'image_url' : url, 'filename' : filename }


def known_file_format(url):
    """
    Check if the url contains known file format extension.
    """
    for extension in FILE_FORMATS:
        if extension in url:
            return extension
    return None


def get_link_to_comments(div):
    """
    Get a link to a comment section.
    """
    li = div.find('li', attrs={'class' : 'first'})
    #return ''.join(['https://www.reddit.com', li.a['href']])
    return li.a['href']


def get_post_timestamp(div):
    """
    Get time and date when post was created.
    """
    time = div.find('time')
    return time['datetime'] if time.has_attr('datetime') else None


def get_p_title_tag(div):
    """
    Get <p> tag with class="title".
    """
    return div.find('p', attrs={'class' : 'title'})


def get_post_url(div):
    """
    Get url of a post.
    """
    p = get_p_title_tag(div)
    return p.a['href']


def get_post_domain(div):
    """
    Get domain of a post.
    """
    p = get_p_title_tag(div)
    span = p.find('span', attrs={'class' : 'domain'})
    return span.a.string


def get_post_title(div):
    """
    Get title of a post.
    """
    return get_p_title_tag(div).a.string


if __name__ == '__main__':
    verbose, pages, url, destination = parse_arguments()

    if not pages: pages = 0
    images = get_all_posts(url, pages)

    print(images)
    #print(next_page)
    print(len(images))
    print_all_domains(get_all_domains(images))

    print()
    print(count_downloadable_images(images))
