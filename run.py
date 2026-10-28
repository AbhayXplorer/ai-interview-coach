#!/usr/bin/env python3
"""
Main Execution Script for AI Technical Interview Coach.
College Seminar Project - Day 2, Session B: Generative AI, RAG & LLM Applications
Presenter: Abhay Gupta (24UICS090)
"""

import os
import sys
import webbrowser
import threading
import time

# Ensure project root in python path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

from web.server import run_server

BANNER = """
================================================================================
   🎓 COLLEGE SEMINAR PRESENTATION & LIVE DEMO
   Topic: An LLM-Powered Technical Interview Coach with Rubric-Based Feedback
          and Code Evaluation
   Presenter: Abhay Gupta (24UICS090)
   Session  : Day 2, Session B (Generative AI, RAG & LLM Applications)
   Time Slot: 09:00 – 09:10 (Strict 10 Minutes Presentation)
================================================================================
   🚀 Starting Local Server...
   📡 Web Interface URL: http://127.0.0.1:8080
   💡 Architecture:
      [1] Subprocess Sandboxed Test Harness (Timeout & SIGKILL Protection)
      [2] Abstract Syntax Tree (AST) Static Complexity & Recursion Analyzer
      [3] Hybrid RAG Pipeline (BM25 + Semantic Search over Rubrics)
      [4] LLM-as-a-Judge 5-Dimensional Rubric Scoring Engine
      [5] Canvas Radar Chart Visualization & 10-Minute Seminar Deck
================================================================================
"""

def open_browser_delayed(url: str, delay: float = 1.0):
    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass
    t = threading.Thread(target=_open, daemon=True)
    t.start()

def main():
    print(BANNER)
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8080))
    host = os.environ.get("HOST", "0.0.0.0")

    # Open browser automatically only if running locally on desktop
    is_cloud = "PORT" in os.environ and "RENDER" in os.environ or "RAILWAY_STATIC_URL" in os.environ
    if "--no-browser" not in sys.argv and not is_cloud:
        open_browser_delayed(f"http://127.0.0.1:{port}")

    try:
        run_server(port=port, host=host)
    except OSError as e:
        if "Address already in use" in str(e):
            alt_port = port + 1
            print(f"[Notice] Port {port} occupied. Switching to port {alt_port}...")
            if "--no-browser" not in sys.argv and not is_cloud:
                open_browser_delayed(f"http://127.0.0.1:{alt_port}")
            run_server(port=alt_port, host=host)
        else:
            raise

if __name__ == "__main__":
    main()
