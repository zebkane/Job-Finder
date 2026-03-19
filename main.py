from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import sqlite3

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

def draw_menu():
  print(" _________________________________ ")
  print("|  -=#=- Zeb's Job Scanner -=#=-  |")
  print("|_________________________________|")
  print("| 1) Run Scan                     |")
  print("| 2) Add Job Site URL             |")
  print("| 3) Add Seach Term               |")
  print("| 4) Exit                         |")
  print("|_________________________________|\n")


def get_menu_choice():
  draw_menu()

  choice = input("Choice: ")
  while not choice.isdigit():
    print("Choice needs to be a number")
    choice = input("Choice: ")

  return int(choice)


def handle_menu_choice(choice):
  if choice == 1:
    handle_scan()
  elif choice == 2:
    pass
  elif choice == 3:
    pass
  elif choice == 4:
    exit()
  else:
    print("Please choose an option 1 - 4")
    return


def handle_scan():
  print("Searching jobs...")

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
        print(match["text"], match["url"])

    browser.close()


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
  while True:
    choice = get_menu_choice()
    handle_menu_choice(choice)




if __name__ == '__main__':
  main()
