from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from InquirerPy import inquirer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import sqlite3

DB_FILE = "job_scanner.db"

job_site_urls = []
search_terms = []

console = Console()


def init_db():
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_site_urls (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      url TEXT UNIQUE NOT NULL
    )
  """)

  cursor.execute("""
    CREATE TABLE IF NOT EXISTS search_terms (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      term TEXT UNIQUE NOT NULL
    )
  """)

  conn.commit()
  conn.close()


def load_data():
  global job_site_urls, search_terms

  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  cursor.execute("SELECT url FROM job_site_urls ORDER BY id")
  job_site_urls = [row[0] for row in cursor.fetchall()]

  cursor.execute("SELECT term FROM search_terms ORDER BY id")
  search_terms = [row[0] for row in cursor.fetchall()]

  conn.close()


def add_job_site_url(url):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  cursor.execute("INSERT OR IGNORE INTO job_site_urls (url) VALUES (?)", (url,))
  conn.commit()
  conn.close()

  load_data()


def add_search_term(term):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  cursor.execute("INSERT OR IGNORE INTO search_terms (term) VALUES (?)", (term,))
  conn.commit()
  conn.close()

  load_data()


def remove_job_site_url(url):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  cursor.execute("DELETE FROM job_site_urls WHERE url = ?", (url,))
  conn.commit()
  conn.close()

  load_data()


def remove_search_term(term):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  cursor.execute("DELETE FROM search_terms WHERE term = ?", (term,))
  conn.commit()
  conn.close()

  load_data()


def draw_menu():
  console.print()
  return inquirer.select(
    message="Select an option:",
    choices=[
      {"name": "Run Scan", "value": 1},
      {"name": "Add Job Site URL", "value": 2},
      {"name": "Add Search Term", "value": 3},
      {"name": "View Job Site URLs", "value": 4},
      {"name": "View Search Terms", "value": 5},
      {"name": "Remove Job Site URL", "value": 6},
      {"name": "Remove Search Term", "value": 7},
      {"name": "Exit", "value": 8},
    ],
    pointer=">",
  ).execute()


def handle_menu_choice(choice):
  if choice == 1:
    handle_scan()
  elif choice == 2:
    url = inquirer.text(message="Enter job site URL:").execute()
    if url:
      add_job_site_url(url)
      console.print(f"[green]Added URL:[/green] {url}")
  elif choice == 3:
    term = inquirer.text(message="Enter search term:").execute()
    if term:
      add_search_term(term)
      console.print(f"[green]Added search term:[/green] {term}")
  elif choice == 4:
    handle_view_job_site_urls()
  elif choice == 5:
    handle_view_search_terms()
  elif choice == 6:
    handle_remove_job_site_url()
  elif choice == 7:
    handle_remove_search_term()
  elif choice == 8:
    exit()


def handle_scan():
  if not job_site_urls:
    console.print("[yellow]No job site URLs saved[/yellow]")
    return

  if not search_terms:
    console.print("[yellow]No search terms saved[/yellow]")
    return

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

      except Exception:
        console.print(f"[red]Failed to scan {url}[/red]")

    browser.close()


def handle_view_job_site_urls():
  console.print(Panel.fit("[bold cyan]Saved Job Site URLs[/bold cyan]", border_style="cyan"))

  if not job_site_urls:
    console.print("[yellow]No job site URLs saved[/yellow]")
    return

  table = Table(show_header=True, header_style="bold magenta")
  table.add_column("#", style="dim", width=4)
  table.add_column("URL", overflow="fold")

  for i, url in enumerate(job_site_urls, start=1):
    table.add_row(str(i), url)

  console.print(table)


def handle_view_search_terms():
  console.print(Panel.fit("[bold cyan]Saved Search Terms[/bold cyan]", border_style="cyan"))

  if not search_terms:
    console.print("[yellow]No search terms saved[/yellow]")
    return

  table = Table(show_header=True, header_style="bold magenta")
  table.add_column("#", style="dim", width=4)
  table.add_column("Search Term", overflow="fold")

  for i, term in enumerate(search_terms, start=1):
    table.add_row(str(i), term)

  console.print(table)


def handle_remove_job_site_url():
  if not job_site_urls:
    console.print("[yellow]No job site URLs to remove.[/yellow]")
    return

  url = inquirer.select(
    message="Select a job site URL to remove:",
    choices=[
      {"name": "Cancel", "value": "iwanttocencel"},
      *[{"name": url, "value": url} for url in job_site_urls]
    ],
    pointer=">",
  ).execute()

  if url == "iwanttocencel":
    return

  remove_job_site_url(url)
  console.print(f"[red]Removed URL:[/red] {url}")


def handle_remove_search_term():
  if not search_terms:
    console.print("[yellow]No search terms to remove[/yellow]")
    return

  term = inquirer.select(
    message="Select a search term to remove:",
    choices=[
      {"name": "Cancel", "value": "iwanttocencel"},
      *[{"name": term, "value": term} for term in search_terms]
    ],
    pointer=">",
  ).execute()

  if term == "iwanttocencel":
    return

  remove_search_term(term)
  console.print(f"[red]Removed search term:[/red] {term}")


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
  init_db()
  load_data()

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
