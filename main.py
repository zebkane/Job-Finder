from urllib.parse import urljoin
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from InquirerPy import inquirer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import sqlite3
import hashlib
import json
import csv
import os
import time
from datetime import datetime

# Contants

DB_FILE = "job_scanner.db"

console = Console()

NEXT_SELECTORS = [
  (By.CSS_SELECTOR, "[data-ph-at-id='pagination-next-link']"),
  (By.CSS_SELECTOR, "a.next-btn"),
  (By.CSS_SELECTOR, "a[aria-label='View next page']"),
  (By.CSS_SELECTOR, "a[aria-label*='next']"),
  (By.CSS_SELECTOR, "button[aria-label*='next']"),
  (By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next')]"),
  (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next')]"),
  (By.CSS_SELECTOR, "a[rel='next']"),
]

LOAD_MORE_SELECTORS = [
  (By.CSS_SELECTOR, "[data-ph-at-id='load-more']"),
  (By.CSS_SELECTOR, "[data-ph-at-id*='load']"),
  (By.CSS_SELECTOR, "button.load-more"),
  (By.CSS_SELECTOR, "a.load-more"),
  (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'load more')]"),
  (By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'load more')]"),
  (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show more')]"),
  (By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show more')]"),
  (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'view more')]"),
  (By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'view more')]"),
  (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'more jobs')]"),
  (By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'more jobs')]"),
  (By.CSS_SELECTOR, "button[aria-label*='load']"),
  (By.CSS_SELECTOR, "a[aria-label*='load']"),
  (By.CSS_SELECTOR, "button[aria-label*='more']"),
  (By.CSS_SELECTOR, "a[aria-label*='more']"),
]

BLOCKED_MARKERS = [
  '<div id="challenge-stage"',
  '<div id="cf-challenge-running"',
  "cf-turnstile-response",
  "managed-challenge",
  "challenge-platform/scripts",
  "ray-id",
]


# Database stuff


def init_db():
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_site_urls (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      url TEXT UNIQUE NOT NULL,
      load_mode TEXT NOT NULL
    )
  """)

  cursor.execute("""
    CREATE TABLE IF NOT EXISTS search_terms (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      term TEXT UNIQUE NOT NULL
    )
  """)

  cursor.execute("""
    CREATE TABLE IF NOT EXISTS scan_results (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      result_hash TEXT UNIQUE NOT NULL,
      site_url TEXT NOT NULL,
      job_title TEXT NOT NULL,
      job_url TEXT NOT NULL,
      first_seen TEXT NOT NULL,
      last_seen TEXT NOT NULL
    )
  """)

  conn.commit()
  conn.close()


# Get


def get_job_sites():
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  cursor.execute("SELECT url, load_mode FROM job_site_urls ORDER BY id")
  sites = [
    {
      "url": row[0],
      "load_mode": row[1],
    }
    for row in cursor.fetchall()
  ]

  conn.close()
  return sites


def get_search_terms():
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  cursor.execute("SELECT term FROM search_terms ORDER BY id")
  terms = [row[0] for row in cursor.fetchall()]

  conn.close()
  return terms


# Add


def add_job_site_url(url, load_mode):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  cursor.execute(
    "INSERT OR IGNORE INTO job_site_urls (url, load_mode) VALUES (?, ?)",
    (url, load_mode)
  )
  conn.commit()
  conn.close()


def add_search_term(term):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  cursor.execute("INSERT OR IGNORE INTO search_terms (term) VALUES (?)", (term,))
  conn.commit()
  conn.close()


# Remove


def remove_job_site_url(url):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  cursor.execute("DELETE FROM job_site_urls WHERE url = ?", (url,))
  cursor.execute("DELETE FROM scan_results WHERE site_url = ?", (url,))
  conn.commit()
  conn.close()


def remove_search_term(term):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  cursor.execute("DELETE FROM search_terms WHERE term = ?", (term,))
  conn.commit()
  conn.close()


def make_result_hash(site_url, job_title, job_url):
  raw = f"{site_url}|{job_title}|{job_url}"
  return hashlib.sha256(raw.encode()).hexdigest()


def update_insert_scan_result(site_url, job_title, job_url):
  now = datetime.now().isoformat()
  result_hash = make_result_hash(site_url, job_title, job_url)

  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  cursor.execute("SELECT id FROM scan_results WHERE result_hash = ?", (result_hash,))
  existing = cursor.fetchone()

  if existing:
    cursor.execute(
      "UPDATE scan_results SET last_seen = ? WHERE result_hash = ?",
      (now, result_hash)
    )
    conn.commit()
    conn.close()
    return False

  cursor.execute(
    "INSERT INTO scan_results (result_hash, site_url, job_title, job_url, first_seen, last_seen) VALUES (?, ?, ?, ?, ?, ?)",
    (result_hash, site_url, job_title, job_url, now, now)
  )
  conn.commit()
  conn.close()
  return True


def get_scan_results(site_url=None):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  if site_url:
    cursor.execute(
      "SELECT site_url, job_title, job_url, first_seen, last_seen FROM scan_results WHERE site_url = ? ORDER BY first_seen DESC",
      (site_url,)
    )
  else:
    cursor.execute(
      "SELECT site_url, job_title, job_url, first_seen, last_seen FROM scan_results ORDER BY first_seen DESC"
    )

  results = [
    {
      "site_url": row[0],
      "job_title": row[1],
      "job_url": row[2],
      "first_seen": row[3],
      "last_seen": row[4],
    }
    for row in cursor.fetchall()
  ]

  conn.close()
  return results


def clear_scan_results():
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  cursor.execute("DELETE FROM scan_results")
  conn.commit()
  conn.close()


# Browser


def create_driver():
  options = Options()
  options.add_argument("--headless=new")
  options.add_argument("--no-sandbox")
  options.add_argument("--disable-dev-shm-usage")
  options.add_argument("--disable-gpu")
  options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36")

  driver = webdriver.Chrome(options=options)
  driver.set_page_load_timeout(30)
  return driver


# Page loading


def is_blocked_page(html):
  html_lower = html.lower()
  return any(marker.lower() in html_lower for marker in BLOCKED_MARKERS)


def wait_for_page_ready(driver, timeout=10):
  deadline = time.time() + timeout
  while time.time() < deadline:
    state = driver.execute_script("return document.readyState")
    if state == "complete":
      break
    time.sleep(0.3)

  last_length = len(driver.page_source)
  stable_checks = 0

  while stable_checks < 3 and time.time() < deadline:
    time.sleep(0.5)
    current_length = len(driver.page_source)

    if current_length == last_length:
      stable_checks += 1
    else:
      stable_checks = 0
      last_length = current_length

  time.sleep(0.5)


def get_page_html(driver, url, load_mode):
  driver.get(url)
  wait_for_page_ready(driver)

  html = driver.page_source
  if is_blocked_page(html):
    return html

  if load_mode == "lazy_load":
    return handle_lazy_load(driver)

  if load_mode == "load_more_button":
    return handle_load_more_button(driver)

  if load_mode == "next_button":
    return handle_next_button(driver)

  return driver.page_source


def get_page_html_with_retry(driver, url, load_mode, retries=2):
  for attempt in range(retries):
    try:
      return get_page_html(driver, url, load_mode)
    except Exception:
      if attempt < retries - 1:
        console.print(f"[yellow]Retry {attempt + 1} for {url}...[/yellow]")
        time.sleep(2)
      else:
        console.print(f"[bold red]Error loading {url}[/bold red]")


# Different page loading styles


def handle_lazy_load(driver, max_rounds=15):
  last_height = driver.execute_script("return document.body.scrollHeight")

  for _ in range(max_rounds):
    current_html = driver.page_source
    if is_blocked_page(current_html):
      return current_html

    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
    wait_for_page_ready(driver)

    current_html = driver.page_source
    if is_blocked_page(current_html):
      return current_html

    new_height = driver.execute_script("return document.body.scrollHeight")
    if new_height == last_height:
      break

    last_height = new_height

  return driver.page_source


def handle_load_more_button(driver, max_clicks=15):
  for _ in range(max_clicks):
    current_html = driver.page_source
    if is_blocked_page(current_html):
      return current_html

    button = find_first_element(driver, LOAD_MORE_SELECTORS)

    if button is None:
      break

    try:
      driver.execute_script("arguments[0].scrollIntoView(true);", button)
      time.sleep(0.5)
      button.click()
      wait_for_page_ready(driver)
    except Exception:
      break

  return driver.page_source


def scroll_to_bottom(driver):
  driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
  wait_for_page_ready(driver)


def find_next_button(driver):
  for by, selector in NEXT_SELECTORS:
    try:
      elements = driver.find_elements(by, selector)
      if elements:
        return elements[0]
    except Exception:
      continue

  return None


def handle_next_button(driver, max_pages=15):
  all_matches = []

  for _ in range(max_pages):
    current_html = driver.page_source
    if is_blocked_page(current_html):
      break

    soup = BeautifulSoup(current_html, "html.parser")
    all_matches.append(soup)

    scroll_to_bottom(driver)

    if is_blocked_page(driver.page_source):
      break

    button = find_next_button(driver)

    if button is None:
      break

    try:
      driver.execute_script("arguments[0].scrollIntoView(true);", button)
      time.sleep(0.5)
      button.click()
      wait_for_page_ready(driver)
    except Exception:
      break

  return all_matches


def find_first_element(driver, selectors):
  for by, selector in selectors:
    try:
      elements = driver.find_elements(by, selector)
      if elements:
        return elements[0]
    except Exception:
      continue

  return None


# Matching


def get_matches(base_url, soup, search_terms):
  matches = []
  seen = set()
  links = soup.find_all("a", href=True)

  for link in links:
    text = link.get_text(" ", strip=True)
    href = link.get("href")

    if not text or not href:
      continue

    full_url = urljoin(base_url, href)

    for search_term in search_terms:
      if search_term.lower() in text.lower():
        key = (text, full_url)

        if key not in seen:
          seen.add(key)
          matches.append({
            "text": text,
            "url": full_url,
          })
        break

  return matches


def get_matches_from_soups(base_url, soups, search_terms):
  all_matches = []
  seen = set()

  for soup in soups:
    page_matches = get_matches(base_url, soup, search_terms)

    for match in page_matches:
      key = (match["text"], match["url"])
      if key not in seen:
        seen.add(key)
        all_matches.append(match)

  return all_matches


# Menu


def draw_menu():
  console.print()
  return inquirer.select(
    message="Select an option:",
    choices=[
      {"name": "Run Scan", "value": "scan"},
      {"name": "Run Scan (New Only)", "value": "scan_new"},
      {"name": "Add Job Site URL", "value": "add_url"},
      {"name": "Add Search Term", "value": "add_term"},
      {"name": "View Job Site URLs", "value": "view_urls"},
      {"name": "View Search Terms", "value": "view_terms"},
      {"name": "View Scan History", "value": "view_history"},
      {"name": "Remove Job Site URL", "value": "remove_url"},
      {"name": "Remove Search Term", "value": "remove_term"},
      {"name": "Clear Scan History", "value": "clear_history"},
      {"name": "Export Results", "value": "export"},
      {"name": "Exit", "value": "exit"},
    ],
    pointer=">",
  ).execute()


def handle_menu_choice(choice):
  if choice == "scan":
    handle_scan(new_only=False)
  elif choice == "scan_new":
    handle_scan(new_only=True)
  elif choice == "add_url":
    handle_add_job_site_url()
  elif choice == "add_term":
    term = inquirer.text(message="Enter search term:").execute()
    if term:
      add_search_term(term)
      console.print(f"[green]Added search term:[/green] {term}")
  elif choice == "view_urls":
    handle_view_job_site_urls()
  elif choice == "view_terms":
    handle_view_search_terms()
  elif choice == "view_history":
    handle_view_scan_history()
  elif choice == "remove_url":
    handle_remove_job_site_url()
  elif choice == "remove_term":
    handle_remove_search_term()
  elif choice == "clear_history":
    handle_clear_scan_history()
  elif choice == "export":
    handle_export()
  elif choice == "exit":
    exit()


# Menu handlers


def handle_add_job_site_url():
  url = inquirer.text(message="Enter job site URL:").execute()
  if not url:
    return

  load_mode = inquirer.select(
    message="Select loading type for this site:",
    choices=[
      {"name": "Nothing", "value": "none"},
      {"name": "Lazy Load", "value": "lazy_load"},
      {"name": "Next Button", "value": "next_button"},
      {"name": "Load More Button", "value": "load_more_button"},
      {"name": "Cancel", "value": "idonotwanttoaddasiteanymore"},
    ],
    pointer=">",
  ).execute()

  if load_mode == "idonotwanttoaddasiteanymore":
    return

  add_job_site_url(url, load_mode)
  console.print(f"[green]Added URL:[/green] {url}")
  console.print(f"[green]Load mode:[/green] {load_mode}")


def handle_scan(new_only=False):
  job_sites = get_job_sites()
  search_terms = get_search_terms()

  if not job_sites:
    console.print("[bold red]No job site URLs saved[/bold red]")
    return

  if not search_terms:
    console.print("[bold red]No search terms saved[/bold red]")
    return

  driver = create_driver()

  try:
    for site in job_sites:
      url = site["url"]
      load_mode = site["load_mode"]

      try:
        if load_mode == "next_button":
          matches = scan_next_button_site(driver, site, search_terms)
        else:
          matches = scan_single_page_site(driver, site, search_terms)

        if matches is None:
          continue

        console.print(
          Panel.fit(
            f"[bold]Matches for[/bold]\n{url}\n[dim]Mode: {load_mode}[/dim]",
            border_style="cyan"
          )
        )

        if not matches:
          console.print("[bold red]No matches found[/bold red]")
          continue

        display_matches(matches, url, new_only)

      except Exception:
        console.print(f"[bold red]Failed to scan {url}[/bold red]")

  finally:
    driver.quit()


def scan_single_page_site(driver, site, search_terms):
  url = site["url"]
  load_mode = site["load_mode"]

  html = get_page_html_with_retry(driver, url, load_mode)

  if html is None or is_blocked_page(html):
    console.print(
      Panel.fit(
        f"[bold red]Page blocked by anti bot[/bold red]\n{url}",
        border_style="red"
      )
    )
    return None

  soup = BeautifulSoup(html, "html.parser")
  return get_matches(url, soup, search_terms)


def scan_next_button_site(driver, site, search_terms):
  url = site["url"]

  driver.get(url)
  wait_for_page_ready(driver)

  html = driver.page_source
  if is_blocked_page(html):
    console.print(
      Panel.fit(
        f"[bold red]Page blocked by anti bot[/bold red]\n{url}",
        border_style="red"
      )
    )
    return None

  soups = handle_next_button(driver)
  return get_matches_from_soups(url, soups, search_terms)


def display_matches(matches, site_url, new_only):
  table = Table(show_header=True, header_style="bold magenta")
  table.add_column("#", style="dim", width=4)
  table.add_column("Status", width=5)
  table.add_column("Title", overflow="fold")
  table.add_column("URL", style="cyan", no_wrap=True)

  displayed = 0

  for i, match in enumerate(matches, start=1):
    is_new = update_insert_scan_result(site_url, match["text"], match["url"])
    status = "[bold green]NEW[/bold green]" if is_new else "[dim]seen[/dim]"

    if new_only and not is_new:
      continue

    displayed += 1
    linked_url = f"[link={match['url']}]{match['url']}[/link]"
    table.add_row(str(i), status, match["text"], linked_url)

  if displayed == 0:
    console.print("[dim]No new matches since last scan[/dim]")
    return

  console.print(table)

  new_count = sum(1 for match in matches if update_insert_scan_result(site_url, match["text"], match["url"]) is False)
  total = len(matches)
  console.print(f"[dim]Total: {total} | Showing: {displayed}[/dim]")


def handle_view_job_site_urls():
  job_sites = get_job_sites()

  console.print(Panel.fit("[bold cyan]Saved Job Site URLs[/bold cyan]", border_style="cyan"))

  if not job_sites:
    console.print("[bold red]No job site URLs saved[/bold red]")
    return

  table = Table(show_header=True, header_style="bold magenta")
  table.add_column("#", style="dim", width=4)
  table.add_column("URL", overflow="fold")
  table.add_column("Load Mode", style="cyan")

  for i, site in enumerate(job_sites, start=1):
    table.add_row(str(i), site["url"], site["load_mode"])

  console.print(table)


def handle_view_search_terms():
  search_terms = get_search_terms()

  console.print(Panel.fit("[bold cyan]Saved Search Terms[/bold cyan]", border_style="cyan"))

  if not search_terms:
    console.print("[bold red]No search terms saved[/bold red]")
    return

  table = Table(show_header=True, header_style="bold magenta")
  table.add_column("#", style="dim", width=4)
  table.add_column("Search Term", overflow="fold")

  for i, term in enumerate(search_terms, start=1):
    table.add_row(str(i), term)

  console.print(table)


def handle_view_scan_history():
  results = get_scan_results()

  console.print(Panel.fit("[bold cyan]Scan History[/bold cyan]", border_style="cyan"))

  if not results:
    console.print("[bold red]No scan history[/bold red]")
    return

  table = Table(show_header=True, header_style="bold magenta")
  table.add_column("#", style="dim", width=4)
  table.add_column("Title", overflow="fold")
  table.add_column("URL", style="cyan", no_wrap=True)
  table.add_column("First Seen", style="dim")
  table.add_column("Last Seen", style="dim")

  for i, result in enumerate(results, start=1):
    first = result["first_seen"][:16].replace("T", " ")
    last = result["last_seen"][:16].replace("T", " ")
    linked_url = f"[link={result['job_url']}]{result['job_url']}[/link]"
    table.add_row(str(i), result["job_title"], linked_url, first, last)

  console.print(table)
  console.print(f"[dim]Total results: {len(results)}[/dim]")


def handle_remove_job_site_url():
  job_sites = get_job_sites()

  if not job_sites:
    console.print("[bold red]No job site URLs to remove[/bold red]")
    return

  url = inquirer.select(
    message="Select a job site URL to remove:",
    choices=[
      {"name": "Cancel", "value": "pleasecancel"},
      *[
        {
          "name": f'{site["url"]} [{site["load_mode"]}]',
          "value": site["url"]
        }
        for site in job_sites
      ]
    ],
    pointer=">",
  ).execute()

  if url == "pleasecancel":
    return

  remove_job_site_url(url)
  console.print(f"[bold red]Removed URL: {url}[/bold red]")


def handle_remove_search_term():
  search_terms = get_search_terms()

  if not search_terms:
    console.print("[bold red]No search terms to remove[/bold red]")
    return

  term = inquirer.select(
    message="Select a search term to remove:",
    choices=[
      {"name": "Cancel", "value": "yesiwouldliketocancel"},
      *[{"name": term, "value": term} for term in search_terms]
    ],
    pointer=">",
  ).execute()

  if term == "yesiwouldliketocancel":
    return

  remove_search_term(term)
  console.print(f"[bold red]Removed search term:[/bold red] {term}")


def handle_clear_scan_history():
  confirm = inquirer.confirm(
    message="Clear all scan history? This cannot be undone",
    default=False,
  ).execute()

  if confirm:
    clear_scan_results()
    console.print("[bold red]Scan history cleared[/bold red]")


def handle_export():
  results = get_scan_results()

  if not results:
    console.print("[bold red]No scan results to export[/bold red]")
    return

  format_choice = inquirer.select(
    message="Export format:",
    choices=[
      {"name": "Cancel", "value": "idonotwanttoexport"},
      {"name": "CSV", "value": "csv"},
      {"name": "JSON", "value": "json"},
    ],
    pointer=">",
  ).execute()

  if format_choice == "idonotwanttoexport":
    return

  filename = inquirer.text(
    message="Filename (without extension):",
    default="job_results",
  ).execute()

  if not filename:
    return

  if format_choice == "csv":
    export_csv(results, filename)
  elif format_choice == "json":
    export_json(results, filename)


# Exports


def export_csv(results, filename):
  filepath = f"{filename}.csv"

  with open(filepath, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["site_url", "job_title", "job_url", "first_seen", "last_seen"])
    writer.writeheader()
    writer.writerows(results)

  full_path = os.path.abspath(filepath)
  console.print(f"[green]Exported {len(results)} results to:[/green] {full_path}")


def export_json(results, filename):
  filepath = f"{filename}.json"

  with open(filepath, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

  full_path = os.path.abspath(filepath)
  console.print(f"[green]Exported {len(results)} results to:[/green] {full_path}")


def main():
  init_db()

  console.print(
    Panel.fit(
      "[bold white]-=#=- Zeb's Job Scanner -=#=-[/bold white]",
      border_style="white"
    )
  )

  while True:
    choice = draw_menu()
    handle_menu_choice(choice)


if __name__ == '__main__':
  main()
