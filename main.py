from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

job_site_urls = [
  # "https://www.riotgames.com/en/work-with-us",
  # "https://www.rockstargames.com/careers/openings"
  # "https://www.naughtydog.com/openings"
  "https://careers.blizzard.com/global/en/search-results?rk=l-art-animation-sound&sortBy=Most%20relevant"
]

search_terms = [
  "art",
  "artist"
]


def get_matches(base_url, soup):
  matches = []
  links = soup.find_all("a", href=True)

  for link in links:
    text = link.get_text(" ", strip=True)
    href = link.get("href")

    if not text or not href:
      continue

    for search_term in search_terms:
      if search_term.lower() in text.lower():
        matches.append({
          "text": text,
          "url": urljoin(base_url, href),
        })
        break

  return matches


def get_page_html(page, url):
  page.goto(url, wait_until="domcontentloaded", timeout=30000)
  page.wait_for_timeout(3000)
  return page.content()


def main():
  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
      user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
    )

    for url in job_site_urls:
      html = get_page_html(page, url)
      soup = BeautifulSoup(html, "html.parser")
      matches = get_matches(url, soup)

      print(f"\nMatches for {url}:")
      for match in matches:
        print(match["url"], "-", match["text"])

    browser.close()


if __name__ == '__main__':
  main()
