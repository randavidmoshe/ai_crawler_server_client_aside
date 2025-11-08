#!/usr/bin/env python3
"""
Simple HTTP Server for Test Form
Run: python server.py
Then open: http://localhost:8000/test-form.html
"""

import http.server
import socketserver
import os

PORT = 8000

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Allow iframes
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

if __name__ == "__main__":
    Handler = MyHTTPRequestHandler
    
    print("=" * 60)
    print("🚀 Test Form Server Starting...")
    print("=" * 60)
    print(f"\n📍 Server running at: http://localhost:{PORT}")
    print(f"🧪 Open test form: http://localhost:{PORT}/test-form.html")
    print("\n✨ Features included:")
    print("   • Basic fields")
    print("   • Conditional fields (show/hide based on selection)")
    print("   • Dynamic AJAX loading (2-second delay)")
    print("   • Tabs (Details, Address, Preferences)")
    print("   • iframe (Address form) - Level 1")
    print("   • Nested iframe (Contact form) - Level 2!")
    print("   • Shadow DOM (Rating widget)")
    print("   • Hover dropdown (Special options)")
    print("\n⌨️  Press Ctrl+C to stop server\n")
    print("=" * 60)
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Server stopped.")
