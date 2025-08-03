# backend/utils/web_search.py

import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__) # Use module-specific logger

def search_web_ddg(query: str, num_results: int = 3) -> list[dict]:
    """
    Performs a basic web search using DuckDuckGo HTML endpoint.
    Note: This is a simple implementation. For production, consider a more robust search API
    or the `duckduckgo-search` library.
    """
    try:
        ddg_url = "https://html.duckduckgo.com/html/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        params = {
            'q': query,
            'kl': 'us-en',
            's': '0'
        }
        # Use a session for potential connection pooling
        with requests.Session() as session:
            response = session.post(ddg_url, headers=headers, data=params, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            result_divs = soup.find_all('div', class_='result')

            count = 0
            for result_div in result_divs:
                if count >= num_results:
                    break
                # DuckDuckGo HTML structure can change, selectors might need updates
                title_tag = result_div.find('a', class_='result__a')
                snippet_tag = result_div.find('a', class_='result__snippet') # Often the snippet is directly in the div or a child <div>

                if title_tag:
                    title = title_tag.get_text(strip=True)
                    url = title_tag.get('href')
                    # Snippet extraction can be tricky, sometimes it's not in an <a> tag
                    # Let's try getting text from the snippet tag or the result div itself
                    snippet = ""
                    if snippet_tag:
                        snippet = snippet_tag.get_text(strip=True)
                    else:
                        # Fallback: Get text from the result div, excluding the title link text
                        # This is a bit crude but might work
                        title_text_len = len(title)
                        result_text = result_div.get_text(strip=True)
                        if result_text.startswith(title) and len(result_text) > title_text_len:
                             snippet = result_text[title_text_len:].strip()

                    if title and url: # URL is crucial
                        results.append({
                            'title': title,
                            'url': url,
                            'snippet': snippet[:200] + "..." if len(snippet) > 200 else snippet # Truncate long snippets
                        })
                        count += 1
            logger.info(f"DuckDuckGo search for '{query}' returned {len(results)} results.")
            return results
    except requests.exceptions.Timeout:
        logger.error(f"Web search request timed out for query: '{query}'")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Web search request failed for query '{query}': {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing web search results for query '{query}': {e}", exc_info=True)
        return []

# Example usage (if running this file directly for testing):
# if __name__ == "__main__":
#     import os
#     logging.basicConfig(level=logging.INFO)
#     query = "Python programming best practices"
#     results = search_web_ddg(query, num_results=2)
#     print(f"Search results for '{query}':")
#     for i, res in enumerate(results):
#         print(f"{i+1}. {res['title']}")
#         print(f"   URL: {res['url']}")
#         print(f"   Snippet: {res['snippet']}\n---")
