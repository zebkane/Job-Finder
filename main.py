from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from InquirerPy import inquirer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import os

job_site_urls = [
  "asfd.sadfsadf",
  "https://www.riotgames.com/en/work-with-us",
  "https://www.rockstargames.com/careers/openings",
  "https://www.naughtydog.com/openings",
  "https://careers.blizzard.com/global/en/search-results?rk=l-art-animation-sound&sortBy=Most%20relevant"
]

search_terms = [
  "art",
  "artist"
]

console = Console()

def draw_menu():
  console.print()
  return inquirer.select(
    message="Select an option:",
    choices=[
      {"name": "Run Scan", "value": 1},
      {"name": "Add Job Site URL", "value": 2},
      {"name": "Add Search Term", "value": 3},
      {"name": "Exit", "value": 4},
    ],
    pointer=">",
  ).execute()


def handle_menu_choice(choice):
  if choice == 1:
    handle_scan()
  elif choice == 2:
    url = inquirer.text(message="Enter job site URL:").execute()
    if url:
      job_site_urls.append(url)
      console.print(f"[green]Added URL:[/green] {url}")
  elif choice == 3:
    term = inquirer.text(message="Enter search term:").execute()
    if term:
      search_terms.append(term)
      console.print(f"[green]Added search term:[/green] {term}")
  elif choice == 4:
    exit()


def handle_scan():
  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
      user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
    )

    for url in job_site_urls:
      try:
        html = get_page_html(page, url)
        soup = BeautifulSoup(html, "html.parser")
        matches = get_matches(url, soup)

        console.print(Panel.fit(f"[bold]Matches for[/bold]\n{url}", border_style="cyan"))

        if not matches:
          console.print("[red]No matches found[/red]")
          continue

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Title", overflow="fold")
        table.add_column("URL", style="cyan", overflow="fold")

        for i, match in enumerate(matches, start=1):
          table.add_row(str(i), match["text"], match["url"])

        console.print(table)

      except Exception as e:
        console.print(f"[red]Failed to scan {url}[/red]")

    browser.close()

  input("Press enter to continue...")


def get_matches(base_url, soup):
  matches = []
  seen = set()
  links = soup.find_all("a", href=True)

  for link in links:
    text = link.get_text(" ", strip=True)
    href = link.get("href")

    if not text or not href:
      continue

    for search_term in search_terms:
      if search_term.lower() in text.lower():
        full_url = urljoin(base_url, href)
        key = (text, full_url)

        if key not in seen:
          seen.add(key)
          matches.append({
            "text": text,
            "url": full_url,
          })
        break

  return matches


def get_page_html(page, url):
  page.goto(url, wait_until="domcontentloaded", timeout=30000)
  page.wait_for_timeout(3000)
  return page.content()


def main():
  console.print(
    Panel.fit(
      "[bold cyan]-=#=- Zeb's Job Scanner -=#=-[/bold cyan]",
      border_style="white"
    )
  )

  while True:
    choice = draw_menu()
    handle_menu_choice(choice)


if __name__ == '__main__':
  main()
