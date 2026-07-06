import subprocess
import time
import urllib.request
import urllib.error
import json
import sys
import os
import socket

PORT = 10000
BASE_URL = f"http://127.0.0.1:{PORT}"

def is_port_in_use(port):
    with socket.socket(socket.AF_SOCKET, socket.SOCK_STREAM) if hasattr(socket, "AF_SOCKET") else socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def wait_for_server(url, timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(f"{url}/ping", timeout=1) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def run_test(req):
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, res.info(), res.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read().decode("utf-8")
    except Exception as e:
        print(f"Connection error: {e}")
        return None, None, None

def main():
    print("--- Starting FastAPI Verification Server ---")
    
    no_start = "--no-start" in sys.argv or "--external" in sys.argv
    
    server_process = None
    if not no_start:
        if is_port_in_use(PORT):
            print(f"Error: Port {PORT} is already in use. Please stop the existing process.")
            sys.exit(1)

        # Launch uvicorn server as a background subprocess
        # We use sys.executable to ensure we use the same Python interpreter
        server_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(PORT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

    try:
        # Wait for server to start
        if not wait_for_server(BASE_URL):
            print("Error: Server failed to start in time.")
            if server_process:
                stdout, stderr = server_process.communicate(timeout=2)
                print("Stdout:", stdout)
                print("Stderr:", stderr)
            sys.exit(1)
            
        print("Server is up and running. Beginning test cases...\n")
        
        all_passed = True

        # -------------------------------------------------------------
        # Test 1: GET /ping with X-Request-ID
        # -------------------------------------------------------------
        print("Test 1: GET /ping with custom X-Request-ID")
        test_id = "custom-uuid-12345"
        req = urllib.request.Request(f"{BASE_URL}/ping")
        req.add_header("X-Request-ID", test_id)
        status, headers, body = run_test(req)
        
        if status != 200:
            print(f"  [FAIL] Expected 200, got {status}")
            all_passed = False
        else:
            resp_json = json.loads(body)
            header_id = headers.get("X-Request-ID")
            body_id = resp_json.get("request_id")
            
            if header_id == test_id and body_id == test_id:
                print("  [PASS] Request-ID propagated to response headers and JSON body successfully.")
            else:
                print(f"  [FAIL] Propagation failed. Expected {test_id}, got Header: {header_id}, Body: {body_id}")
                all_passed = False

        # -------------------------------------------------------------
        # Test 2: GET /ping without X-Request-ID
        # -------------------------------------------------------------
        print("\nTest 2: GET /ping without X-Request-ID (Auto-generation)")
        req = urllib.request.Request(f"{BASE_URL}/ping")
        status, headers, body = run_test(req)
        
        if status != 200:
            print(f"  [FAIL] Expected 200, got {status}")
            all_passed = False
        else:
            resp_json = json.loads(body)
            header_id = headers.get("X-Request-ID")
            body_id = resp_json.get("request_id")
            
            if header_id and body_id and header_id == body_id:
                # Basic UUID validation (should be a string of length 36)
                if len(header_id) == 36 and header_id.count("-") == 4:
                    print(f"  [PASS] Generated matching UUID: {header_id}")
                else:
                    print(f"  [FAIL] Generated ID is not a valid UUID: {header_id}")
                    all_passed = False
            else:
                print(f"  [FAIL] IDs do not match or are missing. Header: {header_id}, Body: {body_id}")
                all_passed = False

        # -------------------------------------------------------------
        # Test 3 & 4: Rate Limiting and Isolation
        # -------------------------------------------------------------
        print("\nTest 3 & 4: Per-client Rate Limiter (9 requests in 10s window)")
        print("Sending 14 requests using X-Client-Id: clientA...")
        
        client_a_statuses = []
        for i in range(14):
            req = urllib.request.Request(f"{BASE_URL}/ping")
            req.add_header("X-Client-Id", "clientA")
            status, _, _ = run_test(req)
            client_a_statuses.append(status)
            # Small delay to ensure order and avoid socket exhaustion
            time.sleep(0.05)
            
        print(f"  Client A request statuses: {client_a_statuses}")
        
        # Verify first 9 succeeded (200), and remaining 5 rate limited (429)
        first_9_ok = all(s == 200 for s in client_a_statuses[:9])
        last_5_rate_limited = all(s == 429 for s in client_a_statuses[9:])
        
        if first_9_ok and last_5_rate_limited:
            print("  [PASS] clientA correctly rate-limited after 9 requests.")
        else:
            print(f"  [FAIL] Rate limit distribution incorrect. Expected 9 OK followed by 5 429s.")
            all_passed = False

        print("Immediately sending request for X-Client-Id: clientB...")
        req = urllib.request.Request(f"{BASE_URL}/ping")
        req.add_header("X-Client-Id", "clientB")
        status, _, _ = run_test(req)
        if status == 200:
            print("  [PASS] clientB succeeded immediately (isolation works).")
        else:
            print(f"  [FAIL] clientB failed with status {status}")
            all_passed = False

        # -------------------------------------------------------------
        # Test 5: Scoped CORS - Allowed Origin preflight
        # -------------------------------------------------------------
        print("\nTest 5: CORS Preflight for Allowed Origin (https://app-g8swuy.example.com)")
        req = urllib.request.Request(f"{BASE_URL}/ping", method="OPTIONS")
        req.add_header("Origin", "https://app-g8swuy.example.com")
        req.add_header("Access-Control-Request-Method", "GET")
        status, headers, _ = run_test(req)
        
        allow_origin = headers.get("Access-Control-Allow-Origin")
        if status == 200 and allow_origin == "https://app-g8swuy.example.com":
            print(f"  [PASS] OPTIONS preflight succeeded and returned correct origin header: {allow_origin}")
        else:
            print(f"  [FAIL] Preflight failed or header mismatch. Status: {status}, Origin Header: {allow_origin}")
            all_passed = False

        # Test 5b: Scoped CORS - Allowed IITM Origin preflight
        print("Test 5b: CORS Preflight for Allowed IITM Origin (https://seek.onlinedegree.iitm.ac.in)")
        req = urllib.request.Request(f"{BASE_URL}/ping", method="OPTIONS")
        req.add_header("Origin", "https://seek.onlinedegree.iitm.ac.in")
        req.add_header("Access-Control-Request-Method", "GET")
        status, headers, _ = run_test(req)
        
        allow_origin = headers.get("Access-Control-Allow-Origin")
        if status == 200 and allow_origin == "https://seek.onlinedegree.iitm.ac.in":
            print(f"  [PASS] OPTIONS preflight succeeded for IITM sub-domain: {allow_origin}")
        else:
            print(f"  [FAIL] IITM preflight failed. Status: {status}, Origin Header: {allow_origin}")
            all_passed = False

        # Test 5c: Scoped CORS - Allowed workers.dev Origin preflight
        print("Test 5c: CORS Preflight for Allowed workers.dev Origin (https://exam.sanand.workers.dev)")
        req = urllib.request.Request(f"{BASE_URL}/ping", method="OPTIONS")
        req.add_header("Origin", "https://exam.sanand.workers.dev")
        req.add_header("Access-Control-Request-Method", "GET")
        status, headers, _ = run_test(req)
        
        allow_origin = headers.get("Access-Control-Allow-Origin")
        if status == 200 and allow_origin == "https://exam.sanand.workers.dev":
            print(f"  [PASS] OPTIONS preflight succeeded for workers.dev: {allow_origin}")
        else:
            print(f"  [FAIL] workers.dev preflight failed. Status: {status}, Origin Header: {allow_origin}")
            all_passed = False

        # -------------------------------------------------------------
        # Test 6: Scoped CORS - Disallowed Origin preflight
        # -------------------------------------------------------------
        print("\nTest 6: CORS Preflight for Disallowed Origin (https://evil.com)")
        req = urllib.request.Request(f"{BASE_URL}/ping", method="OPTIONS")
        req.add_header("Origin", "https://evil.com")
        req.add_header("Access-Control-Request-Method", "GET")
        status, headers, _ = run_test(req)
        
        allow_origin = headers.get("Access-Control-Allow-Origin")
        if allow_origin is None:
            print("  [PASS] No Access-Control-Allow-Origin header returned for disallowed origin.")
        else:
            print(f"  [FAIL] Disallowed origin returned CORS header: {allow_origin}")
            all_passed = False

        # -------------------------------------------------------------
        # Overall Result
        # -------------------------------------------------------------
        print("\n==============================================")
        if all_passed:
            print("FINAL VERIFICATION RESULT: PASS")
            print("==============================================")
            sys.exit(0)
        else:
            print("FINAL VERIFICATION RESULT: FAIL")
            print("==============================================")
            sys.exit(1)

    finally:
        if server_process:
            # Automatically stop uvicorn server subprocess
            print("\nStopping FastAPI server process...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
            print("Server stopped.")

if __name__ == "__main__":
    main()
