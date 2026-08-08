# HTML fixture provenance

Downloaded once by the agent during Phase 4, saved verbatim, used offline in tests (no network
calls happen during test runs).

- `vi_wikipedia_ho_hoan_kiem.html` — `https://vi.wikipedia.org/wiki/Hồ_Hoàn_Kiếm`, fetched
  2026-08-08. CC BY-SA content. Used to test the **generic** (trafilatura) fallback extractor,
  since no site adapter is configured for `vi.wikipedia.org`.
- `quotes_toscrape_page1.html` — `https://quotes.toscrape.com/page/1/`, fetched 2026-08-08.
  quotes.toscrape.com is a site built by the scraping community specifically for scraping
  practice/tooling tests (no robots.txt restrictions). Used to test the **config-driven site
  adapter** (`config/sites/quotes.toscrape.com.yml`): title/content/paragraph/next_link
  selectors and `strip_selectors`. Not a real novel site — used purely for its stable,
  scraping-friendly HTML structure (title, repeated content blocks, "Next" pagination link).

Both fetched with User-Agent `VietReaderBot/0.1 (personal reading assistant; test fixture
download)`, one request each, no redistribution beyond this local test fixture.
