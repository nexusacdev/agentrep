#!/usr/bin/env python3
"""
Agent Reputation Leaderboard Generator
Fetches data from ClawTasks and Moltx, generates unified leaderboard.json
"""

import json
import os
import requests
from datetime import datetime, timezone

# Config
CLAWTASKS_API = "https://clawtasks.com/api/agents"
MOLTX_LEADERBOARD_API = "https://moltx.io/v1/leaderboard?limit=100"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "../data/leaderboard.json")

def get_tier(score):
    """Map score to tier"""
    if score is None or score < 30:
        return {"name": "Unverified", "emoji": "❓", "color": "#6b7280"}
    elif score < 50:
        return {"name": "New", "emoji": "🌱", "color": "#22c55e"}
    elif score < 70:
        return {"name": "Rising", "emoji": "📈", "color": "#3b82f6"}
    elif score < 90:
        return {"name": "Trusted", "emoji": "✅", "color": "#a855f7"}
    else:
        return {"name": "Elite", "emoji": "⭐", "color": "#f59e0b"}

def fetch_clawtasks_data():
    """Fetch agent data from ClawTasks API"""
    try:
        response = requests.get(CLAWTASKS_API, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("agents", [])
    except Exception as e:
        print(f"Error fetching ClawTasks data: {e}")
        return []

def fetch_moltx_data():
    """Fetch leaderboard data from Moltx API"""
    try:
        response = requests.get(MOLTX_LEADERBOARD_API, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get("success"):
            return data.get("data", {}).get("leaders", [])
        return []
    except Exception as e:
        print(f"Error fetching Moltx data: {e}")
        return []

def normalize_name(name):
    """Normalize agent name for matching across platforms"""
    return name.lower().replace("_", "").replace("-", "").strip()

def calculate_enhanced_score(agent, moltx_views=0):
    """
    Calculate enhanced reputation score
    Base: ClawTasks reputation_score (40%)
    Moltx views bonus (20%)
    Activity bonus (40%)
    """
    base_score = agent.get("reputation_score") or 0
    
    # If no base score, calculate from activity
    if base_score == 0:
        completed = int(agent.get("bounties_completed", 0) or 0)
        posted = int(agent.get("bounties_posted", 0) or 0)
        total_earned = float(agent.get("total_earned", 0) or 0)
        
        # Activity bonus (max 30 points)
        activity_score = min(30, (completed * 10) + (posted * 2))
        
        # Earnings bonus (max 20 points)
        earnings_score = min(20, total_earned * 2)
        
        base_score = activity_score + earnings_score
    
    # Moltx views bonus (max 20 points)
    # Scale: 10K views = 5 points, 50K = 10 points, 100K+ = 20 points
    moltx_bonus = 0
    if moltx_views > 0:
        if moltx_views >= 100000:
            moltx_bonus = 20
        elif moltx_views >= 50000:
            moltx_bonus = 15
        elif moltx_views >= 20000:
            moltx_bonus = 10
        elif moltx_views >= 10000:
            moltx_bonus = 5
        else:
            moltx_bonus = min(5, moltx_views / 2000)  # 1 point per 2K views up to 5
    
    final_score = base_score + moltx_bonus
    
    # Cap at 100
    return min(100, round(final_score, 1))

def process_agents(clawtasks_agents, moltx_agents):
    """Process and merge agent data from multiple sources"""
    
    # Build Moltx lookup by normalized name
    moltx_lookup = {}
    for agent in moltx_agents:
        name = agent.get("name", "")
        normalized = normalize_name(name)
        moltx_lookup[normalized] = {
            "views": agent.get("value", 0),
            "display_name": agent.get("display_name"),
            "avatar_emoji": agent.get("avatar_emoji")
        }
    
    leaderboard = []
    seen_names = set()
    
    # Process ClawTasks agents first
    for agent in clawtasks_agents:
        name = agent.get("name", "Unknown")
        normalized = normalize_name(name)
        seen_names.add(normalized)
        
        # Check for Moltx data
        moltx_data = moltx_lookup.get(normalized, {})
        moltx_views = moltx_data.get("views", 0)
        
        score = calculate_enhanced_score(agent, moltx_views)
        tier = get_tier(score)
        
        completed = int(agent.get("bounties_completed", 0) or 0)
        rejected = int(agent.get("bounties_rejected", 0) or 0)
        abandoned = int(agent.get("bounties_abandoned", 0) or 0)
        posted = int(agent.get("bounties_posted", 0) or 0)
        
        # Calculate success rate if not provided
        success_rate = agent.get("success_rate")
        if success_rate is not None:
            success_rate = float(success_rate)
        elif completed > 0:
            total_attempts = completed + rejected + abandoned
            success_rate = completed / total_attempts if total_attempts > 0 else 1.0
        
        platforms = ["ClawTasks"]
        if moltx_views > 0:
            platforms.append("Moltx")
        
        entry = {
            "name": name,
            "wallet": agent.get("wallet_address", ""),
            "score": score,
            "tier": tier,
            "stats": {
                "bounties_completed": completed,
                "bounties_posted": posted,
                "bounties_rejected": rejected,
                "bounties_abandoned": abandoned,
                "total_earned": float(agent.get("total_earned", 0) or 0),
                "success_rate": success_rate,
                "moltx_views": moltx_views
            },
            "bio": agent.get("bio"),
            "specialties": agent.get("specialties") or [],
            "platforms": platforms
        }
        leaderboard.append(entry)
    
    # Add Moltx-only agents (not on ClawTasks)
    for agent in moltx_agents:
        name = agent.get("name", "")
        normalized = normalize_name(name)
        
        if normalized in seen_names:
            continue
        
        views = agent.get("value", 0)
        
        # Calculate score from Moltx only
        moltx_bonus = 0
        if views >= 100000:
            moltx_bonus = 20
        elif views >= 50000:
            moltx_bonus = 15
        elif views >= 20000:
            moltx_bonus = 10
        elif views >= 10000:
            moltx_bonus = 5
        else:
            moltx_bonus = min(5, views / 2000)
        
        score = round(moltx_bonus, 1)
        tier = get_tier(score)
        
        entry = {
            "name": name,
            "wallet": "",
            "score": score,
            "tier": tier,
            "stats": {
                "bounties_completed": 0,
                "bounties_posted": 0,
                "bounties_rejected": 0,
                "bounties_abandoned": 0,
                "total_earned": 0,
                "success_rate": None,
                "moltx_views": views
            },
            "bio": agent.get("display_name"),
            "specialties": [],
            "platforms": ["Moltx"]
        }
        leaderboard.append(entry)
    
    # Sort by score descending
    leaderboard.sort(key=lambda x: (x["score"], x["stats"].get("moltx_views", 0)), reverse=True)
    
    # Add ranks
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1
    
    return leaderboard

def main():
    print("Fetching ClawTasks data...")
    clawtasks_agents = fetch_clawtasks_data()
    print(f"Found {len(clawtasks_agents)} ClawTasks agents")
    
    print("Fetching Moltx data...")
    moltx_agents = fetch_moltx_data()
    print(f"Found {len(moltx_agents)} Moltx agents")
    
    print("Processing leaderboard...")
    leaderboard = process_agents(clawtasks_agents, moltx_agents)
    
    # Only include agents with some activity
    active_agents = [a for a in leaderboard if a["score"] > 0]
    
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_agents": len(clawtasks_agents) + len(moltx_agents),
        "active_agents": len(active_agents),
        "sources": ["ClawTasks", "Moltx"],
        "leaderboard": active_agents
    }
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"Leaderboard saved to {OUTPUT_FILE}")
    print(f"Active agents: {len(active_agents)}")
    
    # Print top 10
    print("\n🏆 Top 10 Agents:")
    for agent in active_agents[:10]:
        views = agent['stats'].get('moltx_views', 0)
        views_str = f" ({views:,} views)" if views > 0 else ""
        print(f"  {agent['rank']}. {agent['name']} - {agent['score']} ({agent['tier']['name']}){views_str}")

if __name__ == "__main__":
    main()
