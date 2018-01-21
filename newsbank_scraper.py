import requests
import pandas
from bs4 import BeautifulSoup
import re
import urllib
import math
import logging

def get_search_query_url(language='English', year='2017', country='USA', 
                   sourcetype = 'Newspaper', searchterm='climate%20change', page='0'):
    ## TODO: add support for multiple search queries
    ## TODO: Add support for automatic doing %20 for multiword search terms
    ## TODO: Add support for automatic %27 around multiword search terms
    search_URL='http://infoweb.newsbank.com.proxy.uchicago.edu/resources/search/nb?p=WORLDNEWS' \
    '&t=country:{0}!{0}/' \
    'year:{1}!{1}/' \
    'language:{2}!{2}' \
    '/stp:{3}!{3}' \
    '&page={5}&fld0=alltext&val0=%27{4}%27' \
    '&bln1=AND&fld1=YMD_date&val1=&sort=_rank_:D&maxresults=50'
    return search_URL.format(country,year,language,sourcetype,searchterm,page)

def get_max_results(page_content):
    searcher = BeautifulSoup(page_content, 'lxml')
    res_count_div = searcher.find('div', class_ = 'nb-showing-result-count')
    if res_count_div is None:
        raise LookupError('No result count div found!')
    regex = r'of\s(\d*,\d*)\sResults'
    number_str = re.search(regex, res_count_div.text).group(1)
    number = int(number_str.replace(',',''))
    return number

def get_news_from_searchpage(searchpage_content, session):
    URL_prefix = 'http://infoweb.newsbank.com.proxy.uchicago.edu'
    link_finder = BeautifulSoup(searchpage_content, 'lxml')
    news = []
    for article_link in link_finder.find_all('a', class_ = 'nb-doc-link'):
        full_url = urllib.parse.urljoin(URL_prefix, article_link.get('href'))
        logging.info(full_url)
        news.append(extract_news(session.get(full_url).text))
    return pandas.DataFrame(news)

def  get_all_news(language='English', year='2017', country='USA', sourcetype='Newspaper', 
                searchterm='climate%20change', limit=None):
    # TODO: implement a limit of results in order not to get all of them if we don't want to

    results_per_page = 50
    # Requesting initial cookie, initializing session
    header = {
        'Upgrade-Insecure-Requests' : '1',
        'User-Agent' :'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Mobile Safari/537.36'
    }
    session = requests.Session()
    session.headers.update(header)
    mainPage = 'http://infoweb.newsbank.com.proxy.uchicago.edu/resources/?p=AWNB'
    response = session.get(mainPage)
    
    # Initial search, page 0
    searchURL = get_search_query_url(language=language, year=year, country=country, sourcetype=sourcetype,
                                    searchterm=searchterm, page=0)
    searchHeader = {
    'Host' : 'infoweb.newsbank.com.proxy.uchicago.edu',
    'Referer' : 'http://infoweb.newsbank.com.proxy.uchicago.edu/resources/search/nb?p=AWNB&b=results&action=search&fld0=alltext&val0={}&bln1=AND&fld1=YMD_date&val1=&sort=YMD_date%3AD'.format(searchterm),
    'Connection' : 'keep-alive',
    'Accept' : 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    }
    response = session.get(searchURL, headers = searchHeader)
    
    max_results = get_max_results(response.text)

    all_news = get_news_from_searchpage(response.text, session)
    max_pages = math.ceil(max_results/results_per_page)
    max_pages=3
    for page in range(1,max_pages):
        logging.info('New page')
        logging.debug('Current newscount: {}'.format(len(all_news)))
        response = session.get(get_search_query_url(language=language, year=year, country=country,
                                                    sourcetype=sourcetype, searchterm=searchterm, page=page), 
                               headers = searchHeader)
        all_news = pandas.concat([get_news_from_searchpage(response.text, session), all_news], ignore_index=True)
    
    return all_news

def extract_news(news_article_html):
    soup = BeautifulSoup(news_article_html, 'lxml')
    parsDict = {}
    # title
    title0 = soup.find_all('div', {'class' : 'title'})
    title1 = title0[0].text.replace('Hide Details', '')
    title = re.sub(r'\<.*\>', '', title1)
    parsDict['title'] = (title)

    # text
    body = soup.find_all('div', {'class' : 'body'})
    text0 = body[0].text
    text1 = re.sub(r'\n', ' ', text0) #Take out new lines
    text2 = re.sub(r"Source- .+","", text1) #for Times of India
    text = re.sub(r"© .+","", text2) #for allAfrica
    parsDict['text'] = (text)

    # source & date
    source = soup.find_all('div', {'class' : 'source'})
    date = re.findall(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s\d{1,2},\s\d{4}', source[0].text)
    parsDict['date'] = (date[0])

    pat2 = re.compile(r"(.*?)-", re.M)
    newssource = pat2.findall(source[0].text)
    parsDict['source'] = (newssource[0])

    meta = soup.find_all('span', {'class' : 'val'})
    # author    
    author0 = meta[0]
    author = re.sub(r'\<.*\>', '', author0.text) #Take out <>
    parsDict['author'] = (author)

    # section
    section0 = meta[1]
    section = re.sub(r'\<.*\>', '', section0.text) #Take out <>
    parsDict['section'] = (section)
    return parsDict