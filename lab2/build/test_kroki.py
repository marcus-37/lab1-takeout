import urllib.request

src = '''@startuml
skinparam backgroundColor #FFFFFF
class 订单 {
  +订单号: string
  +状态: OrderStatus
}
class 订单明细
订单 "1" -- "1..*" 订单明细
@enduml'''.encode('utf-8')

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
req = urllib.request.Request(
    'https://kroki.io/plantuml/png',
    data=src,
    headers={'Content-Type': 'text/plain', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
)
d = opener.open(req, timeout=60).read()
open(r'C:\Users\marcus\AppData\Local\Temp\opencode\cjk_test.png', 'wb').write(d)
print('bytes', len(d))
