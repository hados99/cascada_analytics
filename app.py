import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import duckdb
from typing import Optional, List
import pandas as pd
from datetime import date

app = FastAPI(title="CASCADA CP Analytics System")

DB_PATH = "cascada_analytics.db"

# Mount static files directory
os.makedirs("static", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)

# Helper function to get database connection
def get_db(read_only=True):
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail="Database file not found. Please run the import script first.")
    return duckdb.connect(DB_PATH, read_only=read_only)

@app.get("/api/filters")
def get_filters():
    """Returns available dimension values and date ranges for filtering."""
    try:
        con = get_db()
        
        # Get date range
        date_range = con.execute("SELECT MIN(target_time), MAX(target_time) FROM cascada_metrics").fetchone()
        min_date = date_range[0].isoformat() if date_range[0] else None
        max_date = date_range[1].isoformat() if date_range[1] else None
        
        # Get unique platforms
        platforms = [row[0] for row in con.execute("SELECT DISTINCT platform FROM cascada_metrics WHERE platform IS NOT NULL ORDER BY platform").fetchall()]
        
        # Get unique channels
        channels = [
            {"id": row[0], "name": row[1]} 
            for row in con.execute("SELECT DISTINCT channel_id, channel_name FROM cascada_metrics WHERE channel_id IS NOT NULL ORDER BY channel_name").fetchall()
        ]
        
        # Get unique genres
        genres = [row[0] for row in con.execute("SELECT DISTINCT genre_name FROM cascada_metrics WHERE genre_name IS NOT NULL AND genre_name != 'ALL' ORDER BY genre_name").fetchall()]
        
        # Get unique providers
        providers = [row[0] for row in con.execute("SELECT DISTINCT provider_name FROM cascada_metrics WHERE provider_name IS NOT NULL AND provider_name != 'ALL' ORDER BY provider_name").fetchall()]
        
        con.close()
        return {
            "date_range": {"min": min_date, "max": max_date},
            "platforms": platforms,
            "channels": channels,
            "genres": genres,
            "providers": providers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def build_where_clause(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    channels: Optional[List[str]] = None,
    genres: Optional[List[str]] = None,
    providers: Optional[List[str]] = None
):
    """Helper to build WHERE clause and parameters from filters."""
    where_parts = []
    params = []
    
    if start_date:
        where_parts.append("target_time >= ?")
        params.append(start_date)
    if end_date:
        where_parts.append("target_time <= ?")
        params.append(end_date)
        
    if platforms:
        where_parts.append(f"platform IN ({','.join(['?'] * len(platforms))})")
        params.extend(platforms)
        
    if channels:
        where_parts.append(f"channel_id IN ({','.join(['?'] * len(channels))})")
        params.extend(channels)
        
    if genres:
        where_parts.append(f"genre_name IN ({','.join(['?'] * len(genres))})")
        params.extend(genres)
        
    if providers:
        where_parts.append(f"provider_name IN ({','.join(['?'] * len(providers))})")
        params.extend(providers)
        
    where_clause = " AND ".join(where_parts) if where_parts else "1=1"
    return where_clause, params

@app.get("/api/overview")
def get_overview(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    platform: Optional[List[str]] = Query(None),
    channel: Optional[List[str]] = Query(None),
    genre: Optional[List[str]] = Query(None),
    provider: Optional[List[str]] = Query(None)
):
    """Returns aggregated high-level KPIs based on filters."""
    try:
        con = get_db()
        where_clause, params = build_where_clause(start_date, end_date, platform, channel, genre, provider)
        
        query = f"""
        SELECT 
            SUM(users)::BIGINT as total_users,
            SUM(active_users_playback_15)::BIGINT as active_users_15s,
            SUM(active_users_playback_180)::BIGINT as active_users_3m,
            SUM(active_users_playback_900)::BIGINT as active_users_15m,
            
            SUM(viewing_time)::BIGINT as viewing_time_total,
            SUM(active_viewing_time_15)::BIGINT as viewing_time_15s,
            SUM(active_viewing_time_180)::BIGINT as viewing_time_3m,
            SUM(active_viewing_time_900)::BIGINT as viewing_time_15m,
            
            SUM(playback_counts)::BIGINT as playback_counts,
            SUM(active_playback_counts_15)::BIGINT as active_playbacks_15s,
            SUM(active_playback_counts_180)::BIGINT as active_playbacks_3m,
            SUM(active_playback_counts_900)::BIGINT as active_playbacks_15m
        FROM cascada_metrics
        WHERE {where_clause}
        """
        
        res = con.execute(query, params).fetchone()
        con.close()
        
        if not res or res[0] is None:
            return {
                "users": {"total": 0, "active_15s": 0, "active_3m": 0, "active_15m": 0},
                "viewing_time": {"total": 0, "active_15s": 0, "active_3m": 0, "active_15m": 0, "per_user_total": 0, "per_user_active_15s": 0, "per_user_active_3m": 0, "per_user_active_15m": 0, "per_user_total_15s": 0, "per_user_total_3m": 0, "per_user_total_15m": 0},
                "playback": {"total": 0, "active_15s": 0, "active_3m": 0, "active_15m": 0, "playback_per_user": 0}
            }
            
        (
            users, active_15s, active_3m, active_15m,
            vt_total, vt_15s, vt_3m, vt_15m,
            pb_total, pb_15s, pb_3m, pb_15m
        ) = res
        
        # Calculate rates and averages safely
        users = users or 0
        active_15s = active_15s or 0
        active_3m = active_3m or 0
        active_15m = active_15m or 0
        vt_total = vt_total or 0
        vt_15s = vt_15s or 0
        vt_3m = vt_3m or 0
        vt_15m = vt_15m or 0
        pb_total = pb_total or 0
        pb_15s = pb_15s or 0
        pb_3m = pb_3m or 0
        pb_15m = pb_15m or 0
        
        return {
            "users": {
                "total": users,
                "active_15s": active_15s,
                "active_3m": active_3m,
                "active_15m": active_15m,
                "active_15s_ratio": round((active_15s / users * 100), 2) if users > 0 else 0,
                "active_3m_ratio": round((active_3m / users * 100), 2) if users > 0 else 0,
                "active_15m_ratio": round((active_15m / users * 100), 2) if users > 0 else 0
            },
            "viewing_time": {
                "total": vt_total,
                "active_15s": vt_15s,
                "active_3m": vt_3m,
                "active_15m": vt_15m,
                # Per User Metrics (Total Hours per User)
                "per_user_total": round((vt_total / users), 2) if users > 0 else 0,
                # Option 1: Engagement (Viewing hours per Active User)
                "per_user_active_15s": round((vt_15s / active_15s), 2) if active_15s > 0 else 0,
                "per_user_active_3m": round((vt_3m / active_3m), 2) if active_3m > 0 else 0,
                "per_user_active_15m": round((vt_15m / active_15m), 2) if active_15m > 0 else 0,
                # Option 2: Efficiency (Viewing hours per Total User)
                "per_user_total_15s": round((vt_15s / users), 2) if users > 0 else 0,
                "per_user_total_3m": round((vt_3m / users), 2) if users > 0 else 0,
                "per_user_total_15m": round((vt_15m / users), 2) if users > 0 else 0
            },
            "playback": {
                "total": pb_total,
                "active_15s": pb_15s,
                "active_3m": pb_3m,
                "active_15m": pb_15m,
                "playback_per_user": round((pb_total / users), 2) if users > 0 else 0,
                "active_15s_ratio": round((pb_15s / pb_total * 100), 2) if pb_total > 0 else 0,
                "active_3m_ratio": round((pb_3m / pb_total * 100), 2) if pb_total > 0 else 0,
                "active_15m_ratio": round((pb_15m / pb_total * 100), 2) if pb_total > 0 else 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trends")
def get_trends(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    platform: Optional[List[str]] = Query(None),
    channel: Optional[List[str]] = Query(None),
    genre: Optional[List[str]] = Query(None),
    provider: Optional[List[str]] = Query(None)
):
    """Returns daily time-series data for trends."""
    try:
        con = get_db()
        where_clause, params = build_where_clause(start_date, end_date, platform, channel, genre, provider)
        
        query = f"""
        SELECT 
            target_time,
            SUM(users)::INTEGER as users,
            SUM(active_users_playback_15)::INTEGER as active_users_15s,
            SUM(active_users_playback_180)::INTEGER as active_users_3m,
            SUM(active_users_playback_900)::INTEGER as active_users_15m,
            SUM(viewing_time)::INTEGER as viewing_time,
            SUM(active_viewing_time_15)::INTEGER as viewing_time_15s,
            SUM(active_viewing_time_180)::INTEGER as viewing_time_3m,
            SUM(active_viewing_time_900)::INTEGER as viewing_time_15m,
            SUM(playback_counts)::INTEGER as playbacks,
            SUM(active_playback_counts_15)::INTEGER as playbacks_15s,
            SUM(active_playback_counts_180)::INTEGER as playbacks_3m,
            SUM(active_playback_counts_900)::INTEGER as playbacks_15m
        FROM cascada_metrics
        WHERE {where_clause}
        GROUP BY target_time
        ORDER BY target_time
        """
        
        res = con.execute(query, params).fetchall()
        con.close()
        
        trends = []
        for row in res:
            trends.append({
                "date": row[0].isoformat() if row[0] else None,
                "users": row[1] or 0,
                "active_users_15s": row[2] or 0,
                "active_users_3m": row[3] or 0,
                "active_users_15m": row[4] or 0,
                "viewing_time": row[5] or 0,
                "viewing_time_15s": row[6] or 0,
                "viewing_time_3m": row[7] or 0,
                "viewing_time_15m": row[8] or 0,
                "playbacks": row[9] or 0,
                "playbacks_15s": row[10] or 0,
                "playbacks_3m": row[11] or 0,
                "playbacks_15m": row[12] or 0
            })
        return trends
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/channel-rankings")
def get_channel_rankings(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    platform: Optional[List[str]] = Query(None),
    genre: Optional[List[str]] = Query(None),
    provider: Optional[List[str]] = Query(None),
    sort_by: str = "users",
    limit: int = 15
):
    """Returns ranked channels based on a metric."""
    valid_sort_columns = {
        "users": "SUM(users)",
        "active_users_15s": "SUM(active_users_playback_15)",
        "active_users_3m": "SUM(active_users_playback_180)",
        "viewing_time": "SUM(viewing_time)",
        "viewing_time_15s": "SUM(active_viewing_time_15)",
        "viewing_time_3m": "SUM(active_viewing_time_180)",
        "playbacks": "SUM(playback_counts)"
    }
    
    if sort_by not in valid_sort_columns:
        sort_by = "users"
        
    try:
        con = get_db()
        where_clause, params = build_where_clause(start_date, end_date, platform, None, genre, provider)
        
        sort_expr = valid_sort_columns[sort_by]
        
        query = f"""
        SELECT 
            channel_id,
            channel_name,
            SUM(users)::INTEGER as users,
            SUM(active_users_playback_15)::INTEGER as active_users_15s,
            SUM(active_users_playback_180)::INTEGER as active_users_3m,
            SUM(viewing_time)::INTEGER as viewing_time,
            SUM(active_viewing_time_15)::INTEGER as viewing_time_15s,
            SUM(active_viewing_time_180)::INTEGER as viewing_time_3m,
            SUM(playback_counts)::INTEGER as playbacks
        FROM cascada_metrics
        WHERE {where_clause}
        GROUP BY channel_id, channel_name
        ORDER BY {sort_expr} DESC
        LIMIT ?
        """
        
        params_with_limit = params + [limit]
        res = con.execute(query, params_with_limit).fetchall()
        con.close()
        
        rankings = []
        for i, row in enumerate(res):
            users_val = row[2] or 0
            active_users_15s_val = row[3] or 0
            active_users_3m_val = row[4] or 0
            viewing_time_val = row[5] or 0
            viewing_time_15s_val = row[6] or 0
            viewing_time_3m_val = row[7] or 0
            
            rankings.append({
                "rank": i + 1,
                "channel_id": row[0],
                "channel_name": row[1],
                "users": users_val,
                "active_users_15s": active_users_15s_val,
                "active_users_3m": active_users_3m_val,
                "viewing_time": viewing_time_val,
                "viewing_time_15s": viewing_time_15s_val,
                "viewing_time_3m": viewing_time_3m_val,
                "playbacks": row[8] or 0,
                # Custom aggregations
                "per_user_active_15s": round((viewing_time_15s_val / active_users_15s_val), 2) if active_users_15s_val > 0 else 0,
                "per_user_active_3m": round((viewing_time_3m_val / active_users_3m_val), 2) if active_users_3m_val > 0 else 0
            })
        return rankings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/platform-breakdown")
def get_platform_breakdown(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    channel: Optional[List[str]] = Query(None),
    genre: Optional[List[str]] = Query(None),
    provider: Optional[List[str]] = Query(None)
):
    """Returns metric breakdowns by platform."""
    try:
        con = get_db()
        where_clause, params = build_where_clause(start_date, end_date, None, channel, genre, provider)
        
        query = f"""
        SELECT 
            platform,
            SUM(users)::INTEGER as users,
            SUM(viewing_time)::INTEGER as viewing_time,
            SUM(playback_counts)::INTEGER as playbacks
        FROM cascada_metrics
        WHERE {where_clause}
        GROUP BY platform
        ORDER BY users DESC
        """
        
        res = con.execute(query, params).fetchall()
        con.close()
        
        breakdown = []
        for row in res:
            breakdown.append({
                "platform": row[0] or "Unknown",
                "users": row[1] or 0,
                "viewing_time": row[2] or 0,
                "playbacks": row[3] or 0
            })
        return breakdown
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/query")
def execute_custom_query(payload: dict):
    """Executes a custom SELECT query on the DuckDB (Read-Only)."""
    sql_query = payload.get("query", "")
    
    # Simple check for safety, although the connection itself is opened as read_only=True
    blocked_keywords = ["insert", "update", "delete", "drop", "alter", "create", "truncate", "grant", "revoke"]
    query_lower = sql_query.lower()
    
    for keyword in blocked_keywords:
        if keyword in query_lower:
            # Check if it's isolated word, not substring
            import re
            if re.search(r'\b' + keyword + r'\b', query_lower):
                raise HTTPException(
                    status_code=400, 
                    detail=f"Security restriction: The database connection is READ-ONLY. Modification keyword '{keyword.upper()}' is blocked."
                )
                
    try:
        # Open in read-only mode explicitly
        con = get_db(read_only=True)
        
        # We fetch it as a pandas dataframe to convert to JSON/dict easily with proper types
        df = con.execute(sql_query).fetch_df()
        con.close()
        
        # Replace NaN/None values for JSON compatibility
        df = df.fillna("")
        
        columns = list(df.columns)
        records = df.to_dict(orient="records")
        
        return {
            "columns": columns,
            "records": records,
            "row_count": len(records)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Serve Frontend SPA
@app.get("/", response_class=HTMLResponse)
def get_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

# Serve other static files
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
