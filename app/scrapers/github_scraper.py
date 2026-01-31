"""
GitHub Scraper
"""

import requests
import time
from datetime import datetime
from typing import List, Dict, Optional
import os

LIMITS = {"api": 200}

CRYPTO_REPOS = {
    "bitcoin": [
        {"owner": "bitcoin", "repo": "bitcoin"},
        {"owner": "bitcoin-core", "repo": "gui"},
    ],
    "ethereum": [
        {"owner": "ethereum", "repo": "go-ethereum"},
        {"owner": "ethereum", "repo": "consensus-specs"},
    ],
    "solana": [
        {"owner": "solana-labs", "repo": "solana"},
    ],
    "cardano": [
        {"owner": "input-output-hk", "repo": "cardano-node"},
    ],
    "crypto": [
        {"owner": "bitcoin", "repo": "bitcoin"},
        {"owner": "ethereum", "repo": "go-ethereum"},
    ],
}


def get_limits():
    """Retourne les limites par méthode"""
    return LIMITS


def scrape_github_discussions(query: str = "bitcoin", limit: int = 50) -> List[Dict]:
    return scrape_github_issues(query, limit)


def scrape_github_issues(query: str = "bitcoin", limit: int = 50) -> List[Dict]:
    posts = []
    seen_ids = set()
    
    github_token = os.environ.get("GITHUB_TOKEN")
    
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Crypto-Sentiment-Analysis/1.0"
    }
    
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    
    try:
        query_lower = query.lower()
        repos = CRYPTO_REPOS.get(query_lower, CRYPTO_REPOS.get("crypto", []))
        
        
        for repo_info in repos:
            if len(posts) >= limit:
                break
            
            owner = repo_info["owner"]
            repo = repo_info["repo"]
            
            try:
                issues_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
                
                response = requests.get(
                    issues_url,
                    headers=headers,
                    params={"per_page": 100, "state": "all"},
                    timeout=10
                )
                
                if response.status_code == 403:
                    break
                
                response.raise_for_status()
                issues = response.json()
                
                for issue in issues:
                    if len(posts) >= limit:
                        break
                    
                    issue_id = str(issue.get("number", ""))
                    if issue_id in seen_ids:
                        continue
                    seen_ids.add(issue_id)
                    
                    title = issue.get("title", "")
                    body = issue.get("body", "")
                    
                    if not title:
                        continue
                    
                    text_lower = (title + " " + body).lower()
                    keywords = [query_lower, "crypto", "blockchain"]
                    if not any(keyword in text_lower for keyword in keywords):
                        continue
                    
                    comments = issue.get("comments", 0)
                    reactions = issue.get("reactions", {})
                    total_reactions = sum([
                        reactions.get("+1", 0),
                        reactions.get("-1", 0),
                        reactions.get("laugh", 0),
                        reactions.get("hooray", 0),
                        reactions.get("confused", 0),
                        reactions.get("heart", 0),
                        reactions.get("rocket", 0),
                        reactions.get("eyes", 0),
                    ])
                    
                    user = issue.get("user", {})
                    username = user.get("login", "Anonymous")
                    created_at = issue.get("created_at", "")
                    html_url = issue.get("html_url", "")
                    
                    posts.append({
                        "id": issue_id,
                        "title": title[:500],
                        "text": body[:2000],
                        "score": comments + total_reactions,
                        "likes": total_reactions,
                        "retweets": comments,
                        "username": username,
                        "created_utc": created_at if created_at else datetime.now().isoformat(),
                        "source": "github",
                        "method": "api",
                        "url": html_url,
                        "repo": f"{owner}/{repo}",
                        "human_label": None
                    })
                
                time.sleep(0.5)
                
            except Exception as e:
                continue
        
        print(f"Done: {len(posts)} issues")
        
    except Exception:
        pass
    
    return posts[:limit]
