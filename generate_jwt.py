# gen_token.py
import jwt, time, os
secret = os.getenv("JWT_SECRET_KEY", "your_secret")
payload = {"sub":"test-user-id","iat":int(time.time()),"exp":int(time.time())+86400}
print(jwt.encode(payload, secret, algorithm="HS256"))
