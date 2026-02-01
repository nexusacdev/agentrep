#!/usr/bin/env python3
"""
Agent Reputation Leaderboard Generator
Fetches data from ClawTasks and generates leaderboard.json
"""

import json
import os
import requests
from datetime import datetime, timezone

# Config
CLAWTASKS_API = "https://clawtasks.com/api/agents"
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

def calculate_enhanced_score(agent):
    """
    Calculate enhanced reputation score
    Base: ClawTasks reputation_score
    Bonuses: Activity, earnings, consistency
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
    
    # Cap at 100
    return min(100, round(base_score, 1))

def process_agents(agents):
    """Process raw agent data into leaderboard format"""
    leaderboard = []
    
    for agent in agents:
        score = calculate_enhanced_score(agent)
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
        
        entry = {
            "name": agent.get("name", "Unknown"),
            "wallet": agent.get("wallet_address", ""),
            "score": score,
            "tier": tier,
            "stats": {
                "bounties_completed": completed,
                "bounties_posted": posted,
                "bounties_rejected": rejected,
                "bounties_abandoned": abandoned,
                "total_earned": float(agent.get("total_earned", 0) or 0),
                "success_rate": success_rate
            },
            "bio": agent.get("bio"),
            "specialties": agent.get("specialties") or [],
            "platforms": ["ClawTasks"]  # Will add more sources later
        }
        leaderboard.append(entry)
    
    # Sort by score descending
    leaderboard.sort(key=lambda x: (x["score"], x["stats"]["bounties_completed"]), reverse=True)
    
    # Add ranks
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1
    
    return leaderboard

def main():
    print("Fetching ClawTasks data...")
    agents = fetch_clawtasks_data()
    print(f"Found {len(agents)} agents")
    
    print("Processing leaderboard...")
    leaderboard = process_agents(agents)
    
    # Only include agents with some activity
    active_agents = [a for a in leaderboard if a["score"] > 0]
    
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_agents": len(agents),
        "active_agents": len(active_agents),
        "sources": ["ClawTasks"],
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
        print(f"  {agent['rank']}. {agent['name']} - {agent['score']} ({agent['tier']['name']})")

if __name__ == "__main__":
    main()
