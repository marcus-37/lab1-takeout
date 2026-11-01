import io
import os

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, '..', '实验2_241880548_王睿阳', 'UI界面')
HTML = os.path.join(BASE, 'html')

CSS = '''
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Microsoft YaHei", "PingFang SC", system-ui, sans-serif; color: #1F2329; background: #F5F6F8; }

/* ---------- 通用 ---------- */
.phone { width: 390px; height: 844px; background: #F5F6F8; overflow: hidden; position: relative; display: flex; flex-direction: column; }
.status { height: 44px; display: flex; align-items: center; justify-content: space-between; padding: 0 18px; font-size: 13px; font-weight: 600; background: #fff; }
.status .right { letter-spacing: 2px; font-size: 11px; color: #4E5969; }
.appbar { height: 50px; background: #fff; display: flex; align-items: center; padding: 0 14px; font-size: 16px; font-weight: 600; border-bottom: 1px solid #F0F1F3; }
.appbar .back { width: 24px; color: #4E5969; font-size: 18px; }
.scroll { flex: 1; overflow: hidden; }
.tabbar { height: 62px; background: #fff; border-top: 1px solid #F0F1F3; display: flex; }
.tabbar div { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 11px; color: #86909C; gap: 3px; }
.tabbar div.on { color: #FF6B2C; font-weight: 600; }
.tabbar span.i { font-size: 17px; line-height: 1; }

.card { background: #fff; border-radius: 12px; }
.muted { color: #86909C; }
.small { font-size: 12px; }
.tiny { font-size: 11px; }
.row { display: flex; align-items: center; }
.between { justify-content: space-between; }
.price { color: #FF6B2C; font-weight: 700; }
.price:before { content: "¥"; font-size: .72em; margin-right: 1px; }
.tag { display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 11px; background: #FFF1E8; color: #FF6B2C; }
.tag.gray { background: #F2F3F5; color: #86909C; }
.tag.green { background: #E8FFEA; color: #00A854; }
.btn { display: inline-flex; align-items: center; justify-content: center; border-radius: 8px; font-weight: 600; }
.btn.primary { background: #FF6B2C; color: #fff; }
.btn.ghost { border: 1px solid #FF6B2C; color: #FF6B2C; background: #fff; }
.btn.gray { background: #F2F3F5; color: #4E5969; }

/* ---------- 桌面端 ---------- */
.desk { width: 1440px; height: 900px; display: flex; background: #F5F6F8; overflow: hidden; }
.side { width: 216px; background: #1F2329; color: #C9CDD4; padding: 22px 0; flex: none; }
.logo { color: #fff; font-size: 17px; font-weight: 700; padding: 0 24px 22px; letter-spacing: 1px; }
.logo em { color: #FF6B2C; font-style: normal; }
.nav a { display: block; padding: 11px 24px; font-size: 14px; color: #C9CDD4; }
.nav a.on { background: #2B3038; color: #fff; box-shadow: inset 3px 0 0 #FF6B2C; }
.main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.topbar { height: 64px; background: #fff; display: flex; align-items: center; justify-content: space-between; padding: 0 26px; border-bottom: 1px solid #F0F1F3; }
.topbar h1 { font-size: 18px; }
.body { flex: 1; padding: 22px 26px; overflow: hidden; }
.panel { background: #fff; border-radius: 12px; padding: 20px; }
.stats { display: flex; gap: 16px; }
.stat { flex: 1; background: #fff; border-radius: 12px; padding: 16px 20px; }
.stat .k { font-size: 12px; color: #86909C; }
.stat .v { font-size: 26px; font-weight: 700; margin-top: 6px; }
.stat .v small { font-size: 12px; font-weight: 400; color: #86909C; margin-left: 4px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; color: #86909C; font-weight: 500; font-size: 12px; padding: 10px 8px; border-bottom: 1px solid #F0F1F3; }
td { padding: 12px 8px; border-bottom: 1px solid #F7F8FA; }
.avatar { width: 30px; height: 30px; border-radius: 50%; background: #FFF1E8; color: #FF6B2C; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; }
'''

def mo(title, body, tab='home', status_txt='12:30'):
    tabs = [('home', '⌂', '点餐'), ('order', '☰', '订单'), ('mine', '☺', '我的')]
    t = ''.join(
        '<div class="%s"><span class="i">%s</span>%s</div>' % ('on' if k == tab else '', i, n)
        for k, i, n in tabs)
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="phone">
  <div class="status"><span>{status_txt}</span><span class="right">▮▮▮ ⌁ 100%</span></div>
  <div class="appbar"><span class="back">‹</span><span style="flex:1;text-align:center;margin-right:24px">{title}</span></div>
  <div class="scroll">{body}</div>
  <div class="tabbar">{t}</div>
</div></body></html>'''


def desk(title, active, body, who='张记小炒 · 店长', badge='营业中'):
    nav = [('点餐看板', '工作台'), ('订单处理', '工作台'), ('菜品与库存', '工作台'),
           ('营业额', '工作台'), ('入驻审核', '管理'), ('订单干预', '管理'), ('操作记录', '管理')]
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="desk">
  <div class="side">
    <div class="logo">校园<em>食光</em> · 运营后台</div>
    <div class="nav">{''.join(f'<a class="{"on" if n == active else ""}">{n}</a>' for n, _ in nav)}</div>
  </div>
  <div class="main">
    <div class="topbar"><h1>{title}</h1><div class="row" style="gap:12px">
      <span class="tag green">{badge}</span><div class="avatar">{who[0]}</div><span class="small muted">{who}</span></div></div>
    <div class="body">{body}</div>
  </div>
</div></body></html>'''


# ---------------- 1 登录 ----------------
ui01 = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="phone" style="background:linear-gradient(160deg,#FF8A4C 0%,#FF6B2C 42%,#FFF 42.1%,#FFF 100%)">
  <div class="status"><span>12:30</span><span class="right">▮▮▮ ⌁ 100%</span></div>
  <div style="padding:54px 30px 0;color:#fff">
    <div style="font-size:30px;font-weight:800;letter-spacing:2px">校园食光</div>
    <div style="margin-top:8px;font-size:13px;opacity:.92">校内点餐 · 三十分钟送到宿舍楼下</div>
  </div>
  <div style="margin:40px 24px 0;background:#fff;border-radius:16px;padding:26px 22px;box-shadow:0 10px 30px rgba(0,0,0,.08)">
    <div style="font-size:16px;font-weight:700;margin-bottom:18px">登录</div>
    <div style="border-bottom:1px solid #F0F1F3;padding:10px 0;font-size:14px;color:#86909C">手机号　138****6602</div>
    <div style="border-bottom:1px solid #F0F1F3;padding:10px 0;font-size:14px;color:#86909C">密　码　••••••••</div>
    <div class="btn primary" style="width:100%;height:46px;margin-top:22px;font-size:15px">登 录</div>
    <div class="row between" style="margin-top:14px"><span class="small muted">注册新账号</span><span class="small" style="color:#FF6B2C">忘记密码</span></div>
  </div>
  <div style="margin:22px 24px 0;background:#fff;border-radius:16px;padding:16px 18px">
    <div class="small muted" style="margin-bottom:10px">登录后按角色进入对应端（RBAC 权限隔离）</div>
    <div class="row" style="gap:8px;flex-wrap:wrap">
      <span class="tag">顾客</span><span class="tag">商家</span><span class="tag">配送人员</span><span class="tag">平台管理员</span>
    </div>
    <div class="tiny muted" style="margin-top:12px;line-height:1.6">账号被封禁时任何角色均无法登录；商家账号与店铺一对一，本期不设店员子账号。</div>
  </div>
  <div class="tiny muted" style="text-align:center;margin-top:auto;padding:18px">仅支持校内配送范围 · 不接入第三方支付</div>
</div></body></html>'''

# ---------------- 2 店铺列表 ----------------
ui02_body = '''
<div style="background:#FF6B2C;padding:14px 16px 22px">
  <div style="background:#fff;border-radius:20px;height:38px;display:flex;align-items:center;padding:0 14px;gap:8px">
    <span class="small muted">⌕</span><span class="small muted">搜索菜品，如「黄焖鸡」</span>
  </div>
  <div class="row" style="gap:16px;margin-top:14px;color:#fff;font-size:12px">
    <span style="border-bottom:2px solid #fff;padding-bottom:3px;font-weight:600">全部</span>
    <span style="opacity:.85">销量优先</span><span style="opacity:.85">距离最近</span><span style="opacity:.85">只看营业中</span>
  </div>
</div>
<div style="padding:12px 12px 0">
  <div class="card" style="padding:14px;margin-bottom:10px">
    <div class="row between"><div style="font-size:15px;font-weight:700">张记小炒 · 三食堂窗口</div><span class="tag green">营业中</span></div>
    <div class="row" style="gap:10px;margin-top:8px"><span class="tiny muted">★ 4.8</span><span class="tiny muted">月售 1260</span><span class="tiny muted">起送 ¥12</span><span class="tiny muted">配送费 ¥2</span></div>
    <div class="row" style="gap:6px;margin-top:10px"><span class="tag gray">现炒</span><span class="tag gray">米饭免费</span></div>
    <div class="tiny" style="margin-top:10px;color:#FF6B2C">8 分钟前有人下单 · 预计 25 分钟送达</div>
  </div>
  <div class="card" style="padding:14px;margin-bottom:10px">
    <div class="row between"><div style="font-size:15px;font-weight:700">阿姨奶茶 · 生活区店</div><span class="tag gray">休息中</span></div>
    <div class="row" style="gap:10px;margin-top:8px"><span class="tiny muted">★ 4.6</span><span class="tiny muted">月售 890</span><span class="tiny muted">起送 ¥10</span></div>
    <div class="tiny" style="margin-top:10px;color:#86909C">休息中：可浏览菜品，暂不可下单</div>
  </div>
  <div class="card" style="padding:14px">
    <div class="row between"><div style="font-size:15px;font-weight:700">兰州拉面 · 一食堂</div><span class="tag green">营业中</span></div>
    <div class="row" style="gap:10px;margin-top:8px"><span class="tiny muted">★ 4.9</span><span class="tiny muted">月售 2011</span><span class="tiny muted">起送 ¥15</span></div>
    <div class="tiny" style="margin-top:10px;color:#FF6B2C">今日份数剩余不多</div>
  </div>
</div>'''
ui02 = mo('校园食光', ui02_body)

# ---------------- 3 店铺与购物车 ----------------
ui03_body = '''
<div style="background:#fff;padding:14px 16px">
  <div class="row between"><div style="font-size:17px;font-weight:700">张记小炒</div><span class="tag green">营业中</span></div>
  <div class="row" style="gap:10px;margin-top:6px"><span class="tiny muted">★ 4.8　月售 1260　预计 25 分钟</span></div>
</div>
<div class="row" style="align-items:flex-start;background:#fff">
  <div style="width:86px;background:#F7F8FA;padding:10px 0">
    <div style="padding:8px 10px;font-size:12px;font-weight:600;background:#fff;border-left:3px solid #FF6B2C">热销</div>
    <div style="padding:9px 10px;font-size:12px;color:#4E5969">盖饭</div>
    <div style="padding:9px 10px;font-size:12px;color:#4E5969">汤类</div>
    <div style="padding:9px 10px;font-size:12px;color:#4E5969">饮品</div>
  </div>
  <div style="flex:1;padding:6px 12px 90px">
    <div class="row between" style="padding:12px 0;border-bottom:1px solid #F7F8FA">
      <div style="display:flex;gap:10px">
        <div style="width:64px;height:64px;border-radius:8px;background:#FFF3EC;display:flex;align-items:center;justify-content:center;font-size:24px">🍚</div>
        <div>
          <div style="font-size:14px;font-weight:600">黄焖鸡米饭</div>
          <div class="tiny muted" style="margin-top:4px">月售 320 · 剩余 6 份</div>
          <div class="price" style="margin-top:6px;font-size:15px">16.00</div>
        </div>
      </div>
      <div class="row" style="gap:8px"><span style="color:#FF6B2C;font-size:18px">＋</span></div>
    </div>
    <div class="row between" style="padding:12px 0;border-bottom:1px solid #F7F8FA">
      <div style="display:flex;gap:10px">
        <div style="width:64px;height:64px;border-radius:8px;background:#FFF3EC;display:flex;align-items:center;justify-content:center;font-size:24px">🥬</div>
        <div>
          <div style="font-size:14px;font-weight:600">青椒肉丝盖饭</div>
          <div class="tiny muted" style="margin-top:4px">月售 210 · 剩余 12 份</div>
          <div class="price" style="margin-top:6px;font-size:15px">14.00</div>
        </div>
      </div>
      <div class="row" style="gap:10px"><span style="color:#FF6B2C;font-size:18px">－</span><span style="font-size:14px">1</span><span style="color:#FF6B2C;font-size:18px">＋</span></div>
    </div>
    <div class="row between" style="padding:12px 0;border-bottom:1px solid #F7F8FA;opacity:.45">
      <div style="display:flex;gap:10px">
        <div style="width:64px;height:64px;border-radius:8px;background:#F2F3F5;display:flex;align-items:center;justify-content:center;font-size:24px">🍲</div>
        <div>
          <div style="font-size:14px;font-weight:600">酸辣汤</div>
          <div class="tiny" style="margin-top:4px;color:#FF6B2C">今日已售罄</div>
          <div class="price" style="margin-top:6px;font-size:15px">5.00</div>
        </div>
      </div>
      <span class="tag gray">售罄</span>
    </div>
    <div class="row between" style="padding:12px 0;border-bottom:1px solid #F7F8FA">
      <div style="display:flex;gap:10px">
        <div style="width:64px;height:64px;border-radius:8px;background:#FFF3EC;display:flex;align-items:center;justify-content:center;font-size:24px">🍜</div>
        <div>
          <div style="font-size:14px;font-weight:600">番茄蛋汤</div>
          <div class="tiny muted" style="margin-top:4px">月售 96 · 剩余 13 份</div>
          <div class="price" style="margin-top:6px;font-size:15px">5.00</div>
        </div>
      </div>
      <div class="row" style="gap:8px"><span style="color:#FF6B2C;font-size:18px">＋</span></div>
    </div>
    <div class="row between" style="padding:12px 0;border-bottom:1px solid #F7F8FA">
      <div style="display:flex;gap:10px">
        <div style="width:64px;height:64px;border-radius:8px;background:#FFF3EC;display:flex;align-items:center;justify-content:center;font-size:24px">🥤</div>
        <div>
          <div style="font-size:14px;font-weight:600">冰可乐</div>
          <div class="tiny muted" style="margin-top:4px">月售 410 · 剩余 68 份</div>
          <div class="price" style="margin-top:6px;font-size:15px">3.00</div>
        </div>
      </div>
      <div class="row" style="gap:8px"><span style="color:#FF6B2C;font-size:18px">＋</span></div>
    </div>
    <div class="row between" style="padding:12px 0">
      <div style="display:flex;gap:10px">
        <div style="width:64px;height:64px;border-radius:8px;background:#FFF3EC;display:flex;align-items:center;justify-content:center;font-size:24px">🍗</div>
        <div>
          <div style="font-size:14px;font-weight:600">卤鸡腿</div>
          <div class="tiny muted" style="margin-top:4px">月售 158 · 剩余 9 份</div>
          <div class="price" style="margin-top:6px;font-size:15px">6.00</div>
        </div>
      </div>
      <div class="row" style="gap:8px"><span style="color:#FF6B2C;font-size:18px">＋</span></div>
    </div>
  </div>
</div>
<div style="position:absolute;left:0;right:0;bottom:62px;background:#2B3038;color:#fff;padding:12px 16px;display:flex;align-items:center;justify-content:space-between">
  <div style="display:flex;align-items:center;gap:10px">
    <div style="width:38px;height:38px;border-radius:50%;background:#FF6B2C;display:flex;align-items:center;justify-content:center">🛒</div>
    <div><div style="font-size:16px;font-weight:700">¥30.00</div><div class="tiny" style="opacity:.7">另需配送费 ¥2 · 已减 0</div></div>
  </div>
  <div class="btn primary" style="height:40px;padding:0 22px">去结算</div>
</div>'''
ui03 = mo('店铺详情', ui03_body, tab='home')

# ---------------- 4 确认订单 ----------------
ui04_body = '''
<div style="padding:12px">
  <div class="card" style="padding:16px;margin-bottom:10px">
    <div class="row between"><div style="font-size:14px;font-weight:700">送到 · 3 号宿舍楼 512</div><span class="small" style="color:#FF6B2C">修改</span></div>
    <div class="tiny muted" style="margin-top:8px">王同学　138****6602</div>
    <div class="tiny" style="margin-top:8px;color:#00A854">✓ 在配送范围内（三片区）</div>
  </div>
  <div class="card" style="padding:16px;margin-bottom:10px">
    <div class="row between" style="margin-bottom:12px"><span style="font-size:14px;font-weight:700">张记小炒</span><span class="tiny muted">价格已锁定</span></div>
    <div class="row between" style="font-size:13px;margin-bottom:8px"><span>黄焖鸡米饭 × 1</span><span>¥16.00</span></div>
    <div class="row between" style="font-size:13px;margin-bottom:8px"><span>青椒肉丝盖饭 × 1</span><span>¥14.00</span></div>
    <div class="row between" style="font-size:13px;color:#86909C"><span>配送费</span><span>¥2.00</span></div>
    <div class="row between" style="margin-top:12px;padding-top:12px;border-top:1px dashed #F0F1F3"><span class="small muted">合计</span><span class="price" style="font-size:18px">32.00</span></div>
  </div>
  <div class="card" style="padding:16px;margin-bottom:10px">
    <div class="row between"><span style="font-size:13px">支付方式</span><span class="small">钱包余额 ¥45.60</span></div>
    <div class="row between" style="margin-top:12px"><span style="font-size:13px">备注</span><span class="tiny muted">少辣，不要香菜</span></div>
    <div class="row between" style="margin-top:12px"><span style="font-size:13px">餐具</span><span class="tiny muted">无需餐具</span></div>
  </div>
  <div class="tiny muted" style="padding:2px 6px;line-height:1.7">提交订单即预占库存并锁定当前价格；30 分钟未支付订单自动取消，库存回补。同一提交令牌重复点击只生成一单。</div>
</div>
<div style="position:absolute;left:0;right:0;bottom:62px;background:#fff;border-top:1px solid #F0F1F3;padding:12px 16px;display:flex;align-items:center;justify-content:space-between">
  <div><span class="tiny muted">应付</span> <span class="price" style="font-size:20px">32.00</span></div>
  <div class="btn primary" style="height:42px;padding:0 26px">提交订单</div>
</div>'''
ui04 = mo('确认订单', ui04_body, tab='order')

# ---------------- 5 订单跟踪 ----------------
ui05_body = '''
<div style="background:#FF6B2C;color:#fff;padding:18px 16px 24px">
  <div style="font-size:18px;font-weight:700">商家接单中</div>
  <div style="margin-top:6px;font-size:12px;opacity:.9">09:32 前未接单将自动取消并全额退款</div>
  <div style="margin-top:14px;background:rgba(255,255,255,.16);border-radius:10px;padding:10px 12px;font-size:12px">订单号 20261025093001 · 张记小炒</div>
</div>
<div style="padding:12px">
  <div class="card" style="padding:18px 16px;margin-bottom:10px">
    <div style="display:flex;gap:12px">
      <div style="display:flex;flex-direction:column;align-items:center;width:14px">
        <div style="width:10px;height:10px;border-radius:50%;background:#FF6B2C"></div>
        <div style="flex:1;width:2px;background:#F0F1F3;margin:4px 0"></div>
        <div style="width:10px;height:10px;border-radius:50%;background:#F0F1F3"></div>
        <div style="flex:1;width:2px;background:#F0F1F3;margin:4px 0"></div>
        <div style="width:10px;height:10px;border-radius:50%;background:#F0F1F3"></div>
      </div>
      <div style="flex:1;display:flex;flex-direction:column;gap:22px">
        <div><div style="font-size:13px;font-weight:600">已支付 · 等待商家接单</div><div class="tiny muted" style="margin-top:3px">09:30</div></div>
        <div><div style="font-size:13px;color:#86909C">制作中 → 待配送</div></div>
        <div><div style="font-size:13px;color:#86909C">骑手取餐 → 已送达 → 确认收货</div></div>
      </div>
    </div>
  </div>
  <div class="card" style="padding:16px;margin-bottom:10px">
    <div class="row between"><div style="font-size:14px;font-weight:700">配送信息</div><span class="tag gray">待派单</span></div>
    <div class="tiny muted" style="margin-top:10px">管理员按片区指派骑手，接单后显示骑手姓名与电话</div>
  </div>
  <div class="card" style="padding:16px">
    <div class="row between"><span style="font-size:13px">黄焖鸡米饭 × 1</span><span class="small">¥16.00</span></div>
    <div class="row between" style="margin-top:8px"><span style="font-size:13px">青椒肉丝盖饭 × 1</span><span class="small">¥14.00</span></div>
    <div class="row between" style="margin-top:8px"><span class="small muted">配送费</span><span class="small">¥2.00</span></div>
    <div class="row between" style="margin-top:12px;padding-top:12px;border-top:1px dashed #F0F1F3"><span class="small">实付</span><span class="price">32.00</span></div>
  </div>
</div>
<div style="position:absolute;left:0;right:0;bottom:62px;background:#fff;border-top:1px solid #F0F1F3;padding:10px 16px;display:flex;gap:10px;justify-content:flex-end">
  <div class="btn ghost" style="height:38px;padding:0 18px;font-size:13px">取消订单</div>
  <div class="btn gray" style="height:38px;padding:0 18px;font-size:13px">联系商家</div>
</div>'''
ui05 = mo('订单详情', ui05_body, tab='order')

# ---------------- 6 商家订单工作台 ----------------
orders_pending = '''
<div class="panel" style="margin-bottom:12px;border-left:4px solid #FF6B2C">
  <div class="row between"><div style="font-weight:700">#0930-0128　3 号宿舍楼 512</div><span class="tag">剩余 06:12 接单</span></div>
  <div class="tiny muted" style="margin-top:8px">黄焖鸡米饭 ×1　青椒肉丝盖饭 ×1　备注：少辣</div>
  <div class="row between" style="margin-top:12px"><span class="price">¥32.00</span>
    <div class="row" style="gap:8px"><span class="btn gray" style="height:34px;padding:0 16px;font-size:13px">拒单</span><span class="btn primary" style="height:34px;padding:0 18px;font-size:13px">接单</span></div></div>
</div>
<div class="panel" style="border-left:4px solid #FF6B2C">
  <div class="row between"><div style="font-weight:700">#0930-0127　5 号宿舍楼 208</div><span class="tag">剩余 08:40 接单</span></div>
  <div class="tiny muted" style="margin-top:8px">兰州拉面 ×2</div>
  <div class="row between" style="margin-top:12px"><span class="price">¥28.00</span>
    <div class="row" style="gap:8px"><span class="btn gray" style="height:34px;padding:0 16px;font-size:13px">拒单</span><span class="btn primary" style="height:34px;padding:0 18px;font-size:13px">接单</span></div></div>
</div>'''

orders_cooking = '''
<div class="panel" style="margin-bottom:12px">
  <div class="row between"><div style="font-weight:700">#0930-0125</div><span class="tag green">制作中 04:20</span></div>
  <div class="tiny muted" style="margin-top:8px">酸辣汤 ×1　黄焖鸡米饭 ×1</div>
  <div class="row between" style="margin-top:12px"><span class="price">¥21.00</span><span class="btn primary" style="height:34px;padding:0 16px;font-size:13px">出餐</span></div>
</div>
<div class="panel">
  <div class="row between"><div style="font-weight:700">#0930-0124</div><span class="tag green">制作中 02:05</span></div>
  <div class="tiny muted" style="margin-top:8px">青椒肉丝盖饭 ×2</div>
  <div class="row between" style="margin-top:12px"><span class="price">¥28.00</span><span class="btn primary" style="height:34px;padding:0 16px;font-size:13px">出餐</span></div>
</div>'''

orders_ready = '''
<div class="panel" style="margin-bottom:12px">
  <div class="row between"><div style="font-weight:700">#0930-0122</div><span class="tag gray">待派单</span></div>
  <div class="tiny muted" style="margin-top:8px">送至 7 号楼 301</div>
  <div class="tiny" style="margin-top:8px;color:#FF6B2C">已呼叫配送，等待管理员指派</div>
</div>
<div class="panel">
  <div class="row between"><div style="font-weight:700">#0930-0121</div><span class="tag green">配送中</span></div>
  <div class="tiny muted" style="margin-top:8px">骑手：李师傅　138****2231</div>
</div>'''

ui06_body = f'''
<div class="stats" style="margin-bottom:18px">
  <div class="stat"><div class="k">今日订单</div><div class="v">126<small>单</small></div></div>
  <div class="stat"><div class="k">今日营业额</div><div class="v">2,148<small>元</small></div></div>
  <div class="stat"><div class="k">待接单</div><div class="v" style="color:#FF6B2C">2<small>单</small></div></div>
  <div class="stat"><div class="k">超时未接单</div><div class="v" style="color:#00A854">0<small>单</small></div></div>
</div>
<div style="display:flex;gap:16px;align-items:flex-start">
  <div style="flex:1"><div class="row between" style="margin-bottom:10px"><b style="font-size:14px">待接单</b><span class="tiny muted">10 分钟未接单自动取消</span></div>{orders_pending}</div>
  <div style="flex:1"><div class="row between" style="margin-bottom:10px"><b style="font-size:14px">制作中</b><span class="tiny muted">出餐后自动转待配送</span></div>{orders_cooking}</div>
  <div style="flex:1"><div class="row between" style="margin-bottom:10px"><b style="font-size:14px">待配送 / 配送中</b><span class="tiny muted">由管理员派单</span></div>{orders_ready}</div>
</div>'''
ui06 = desk('订单工作台', '订单处理', ui06_body)

# ---------------- 7 菜品与库存 ----------------
rows = [
    ('黄焖鸡米饭', '16.00', '40', '6', '21', '售卖中'),
    ('青椒肉丝盖饭', '14.00', '30', '2', '18', '售卖中'),
    ('酸辣汤', '5.00', '20', '0', '20', '已售罄'),
    ('番茄蛋汤', '5.00', '20', '0', '7', '售卖中'),
    ('可乐', '3.00', '100', '0', '32', '售卖中'),
]
trs = ''
for n, p, t, r, s, st in rows:
    badge = '<span class="tag gray">已售罄</span>' if st == '已售罄' else '<span class="tag green">售卖中</span>'
    trs += f'''<tr><td><b>{n}</b></td><td>¥{p}</td><td>{t}</td><td>{r}</td><td>{s}</td><td>{badge}</td>
    <td><span class="small" style="color:#FF6B2C">改价</span>　<span class="small" style="color:#4E5969">设为售罄</span></td></tr>'''

ui07_body = f'''
<div class="panel" style="margin-bottom:16px">
  <div class="row between">
    <div class="row" style="gap:14px"><b>今日库存设置</b><span class="tiny muted">修改份数不影响当日已预占与已售数量，次日 00:00 按设置值重置</span></div>
    <div class="row" style="gap:10px"><span class="btn ghost" style="height:34px;padding:0 16px;font-size:13px">批量设置份数</span><span class="btn primary" style="height:34px;padding:0 16px;font-size:13px">新增菜品</span></div>
  </div>
</div>
<div class="panel">
  <table>
    <thead><tr><th style="width:26%">菜品</th><th>单价</th><th>今日份数</th><th>已预占</th><th>已售</th><th>状态</th><th>操作</th></tr></thead>
    <tbody>{trs}</tbody>
  </table>
  <div class="tiny muted" style="margin-top:14px;line-height:1.8">· 可用份数 = 今日份数 − 已预占 − 已售；预占由顾客提交订单产生，30 分钟未支付自动释放。<br>
  · 改价只影响之后提交的订单，已提交订单一律按下单时价格快照结算。</div>
</div>'''
ui07 = desk('菜品与库存', '菜品与库存', ui07_body)

# ---------------- 8 骑手任务 ----------------
ui08_body = '''
<div style="background:#1F2329;color:#fff;padding:16px">
  <div class="row between"><div><div style="font-size:15px;font-weight:700">李师傅</div><div class="tiny" style="opacity:.65;margin-top:4px">三片区 · 工号 R-018</div></div>
  <div style="background:#00A854;border-radius:20px;padding:5px 12px;font-size:12px">● 接单中</div></div>
  <div class="row" style="margin-top:16px;gap:0">
    <div style="flex:1"><div class="tiny" style="opacity:.6">今日完成</div><div style="font-size:20px;font-weight:700;margin-top:2px">12 单</div></div>
    <div style="flex:1"><div class="tiny" style="opacity:.6">今日收入</div><div style="font-size:20px;font-weight:700;margin-top:2px">¥72.00</div></div>
    <div style="flex:1"><div class="tiny" style="opacity:.6">准时率</div><div style="font-size:20px;font-weight:700;margin-top:2px">98%</div></div>
  </div>
</div>
<div style="padding:12px">
  <div class="tiny muted" style="margin:2px 4px 8px">新任务（管理员按片区指派）</div>
  <div class="card" style="padding:14px;margin-bottom:10px;border-left:4px solid #FF6B2C">
    <div class="row between"><div style="font-weight:700;font-size:15px">张记小炒 · 3 号宿舍楼 512</div><span class="tag">8 分钟前</span></div>
    <div class="tiny muted" style="margin-top:8px">取餐：三食堂二楼 12 号窗口　→　送达：3 号楼 512</div>
    <div class="tiny muted" style="margin-top:6px">订单 #0930-0131　联系顾客 138****6602</div>
    <div class="row between" style="margin-top:12px"><span class="tiny" style="color:#FF6B2C">预计 12 分钟 · 配送费 ¥2</span>
      <div class="row" style="gap:8px"><span class="btn gray" style="height:34px;padding:0 16px;font-size:13px">拒绝</span><span class="btn primary" style="height:34px;padding:0 16px;font-size:13px">接受</span></div></div>
  </div>
  <div class="tiny muted" style="margin:12px 4px 8px">配送中</div>
  <div class="card" style="padding:14px">
    <div class="row between"><div style="font-weight:700;font-size:15px">阿姨奶茶 · 5 号宿舍楼 208</div><span class="tag green">已取餐</span></div>
    <div class="tiny muted" style="margin-top:8px">剩余 1.2 km · 预计 6 分钟送达</div>
    <div class="row" style="gap:8px;margin-top:12px"><span class="btn ghost" style="height:34px;padding:0 16px;font-size:13px">上报异常</span><span class="btn primary" style="height:34px;padding:0 16px;font-size:13px">确认送达</span></div>
  </div>
</div>'''
ui08 = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="phone" style="background:#F5F6F8">
  <div class="status"><span>12:30</span><span class="right">▮▮▮ ⌁ 100%</span></div>
  <div class="scroll">{ui08_body}</div>
  <div class="tabbar"><div class="on"><span class="i">☰</span>任务</div><div><span class="i">￥</span>收入</div><div><span class="i">☺</span>我的</div></div>
</div></body></html>'''

# ---------------- 9 骑手上报异常 ----------------
ui09_body = '''
<div style="height:210px;background:linear-gradient(135deg,#DCE9F7,#EAF3FF);position:relative;display:flex;align-items:center;justify-content:center">
  <div style="position:absolute;left:28%;top:34%;width:80px;height:3px;background:#FF6B2C;transform:rotate(-18deg);border-radius:2px"></div>
  <div style="width:12px;height:12px;border-radius:50%;background:#FF6B2C;margin-right:70px"></div>
  <div style="width:12px;height:12px;border-radius:50%;background:#33507A;margin-left:70px"></div>
  <div class="tiny muted" style="position:absolute;bottom:8px;right:10px">示意：起点 → 终点</div>
</div>
<div style="padding:12px">
  <div class="card" style="padding:16px;margin-bottom:10px">
    <div class="row between"><div style="font-weight:700">配送异常上报</div><span class="tag gray">订单 #0930-0131</span></div>
    <div class="tiny muted" style="margin-top:8px;line-height:1.7">上报后订单转为「配送异常」并挂起，不再计入当前任务，由管理员在后台处置（改派或取消退款）。</div>
  </div>
  <div class="card" style="padding:14px;margin-bottom:10px">
    <div class="small muted" style="margin-bottom:10px">请选择原因（必填）</div>
    <div class="row between" style="padding:12px 0;border-bottom:1px solid #F7F8FA"><span style="font-size:14px">联系不上顾客</span><span style="color:#FF6B2C">●</span></div>
    <div class="row between" style="padding:12px 0;border-bottom:1px solid #F7F8FA"><span style="font-size:14px">地址错误</span><span style="color:#D9DCE1">○</span></div>
    <div class="row between" style="padding:12px 0"><span style="font-size:14px">无人收货</span><span style="color:#D9DCE1">○</span></div>
  </div>
  <div class="card" style="padding:14px">
    <div class="small muted" style="margin-bottom:8px">补充说明</div>
    <div style="min-height:60px;font-size:13px;color:#4E5969">已拨打 3 次，无人接听；已在 512 门口等待 10 分钟。</div>
    <div class="tiny muted" style="margin-top:10px">现场照片（选填）　<span class="tag gray">＋ 上传</span></div>
  </div>
</div>
<div style="position:absolute;left:0;right:0;bottom:0;background:#fff;border-top:1px solid #F0F1F3;padding:12px 16px;display:flex;gap:10px">
  <div class="btn gray" style="flex:1;height:44px">返回</div>
  <div class="btn primary" style="flex:2;height:44px">提交异常</div>
</div>'''
ui09 = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="phone">
  <div class="status"><span>12:30</span><span class="right">▮▮▮ ⌁ 100%</span></div>
  <div class="appbar"><span class="back">‹</span><span style="flex:1;text-align:center;margin-right:24px">配送详情</span></div>
  <div class="scroll">{ui09_body}</div>
</div></body></html>'''

# ---------------- 10 入驻审核 ----------------
apply_rows = '''
<tr><td><b>阿姨奶茶 · 生活区店</b><div class="tiny muted" style="margin-top:4px">提交于 10-24 15:20</div></td>
<td>餐饮服务 · 饮品</td><td>食品经营许可证 2024-0312</td><td><span class="tag">待审核</span></td>
<td><span class="btn ghost" style="height:30px;padding:0 14px;font-size:12px">驳回</span> <span class="btn primary" style="height:30px;padding:0 14px;font-size:12px">通过</span></td></tr>
<tr><td><b>兰州拉面 · 一食堂</b><div class="tiny muted" style="margin-top:4px">提交于 10-24 11:02</div></td>
<td>餐饮服务 · 面食</td><td>食品经营许可证 2024-0088</td><td><span class="tag">待审核</span></td>
<td><span class="btn ghost" style="height:30px;padding:0 14px;font-size:12px">驳回</span> <span class="btn primary" style="height:30px;padding:0 14px;font-size:12px">通过</span></td></tr>
<tr><td><b>鲜果盒子</b><div class="tiny muted" style="margin-top:4px">提交于 10-23 19:45</div></td>
<td>零售 · 水果</td><td>营业执照 9131******</td><td><span class="tag green">已通过</span></td>
<td><span class="small muted">审核人：平台运营 / 10-24</span></td></tr>'''

ui10_body = f'''
<div class="stats" style="margin-bottom:16px">
  <div class="stat"><div class="k">待审核</div><div class="v" style="color:#FF6B2C">2</div></div>
  <div class="stat"><div class="k">本月通过</div><div class="v">7</div></div>
  <div class="stat"><div class="k">本月驳回</div><div class="v">3</div></div>
  <div class="stat"><div class="k">在营店铺</div><div class="v">19</div></div>
</div>
<div class="panel">
  <div class="row between" style="margin-bottom:6px"><b>商家入驻申请</b><span class="tiny muted">审核通过前店铺不可营业、不可上架菜品</span></div>
  <table><thead><tr><th style="width:28%">店铺</th><th>类目</th><th>资质</th><th>状态</th><th>操作</th></tr></thead>
  <tbody>{apply_rows}</tbody></table>
  <div class="tiny muted" style="margin-top:16px">驳回必须填写原因并通知商家；通过与驳回都会写入操作记录（操作人 / 时间 / 对象 / 原因）。</div>
</div>'''
ui10 = desk('商家入驻审核', '入驻审核', ui10_body, '平台运营 · 管理员', '平台侧')

# ---------------- 11 订单干预与仲裁 ----------------
logs = '''
<tr><td>09:30:12</td><td>顾客 王同学</td><td>提交订单</td><td>—</td><td>待支付</td></tr>
<tr><td>09:30:48</td><td>支付服务</td><td>余额支付成功</td><td>待支付</td><td>待接单</td></tr>
<tr><td>09:31:20</td><td>商家 张记小炒</td><td>接单</td><td>待接单</td><td>制作中</td></tr>
<tr><td>09:38:05</td><td>商家 张记小炒</td><td>出餐</td><td>制作中</td><td>待配送</td></tr>
<tr><td>09:40:31</td><td>管理员</td><td>派单给 R-018</td><td>待配送</td><td>配送中</td></tr>
<tr><td>09:52:10</td><td>骑手 R-018</td><td>上报配送失败</td><td>配送中</td><td>配送异常</td></tr>
<tr><td>09:55:02</td><td>管理员</td><td>强制退款 ¥32.00</td><td>配送异常</td><td>已取消</td></tr>'''

ui11_body = f'''
<div style="display:flex;gap:16px;align-items:flex-start">
  <div style="flex:1.1">
    <div class="panel" style="margin-bottom:16px">
      <div class="row between"><b>订单 #0930-0131</b><span class="tag">配送异常 · 待处置</span></div>
      <div class="tiny muted" style="margin-top:10px">顾客：王同学 138****6602　｜　店铺：张记小炒　｜　实付 ¥32.00</div>
      <div class="tiny muted" style="margin-top:6px">地址：3 号宿舍楼 512　｜　骑手：李师傅（R-018）　｜　异常原因：联系不上顾客</div>
      <div class="row" style="gap:10px;margin-top:16px">
        <span class="btn primary" style="height:36px;padding:0 18px;font-size:13px">改派骑手</span>
        <span class="btn ghost" style="height:36px;padding:0 18px;font-size:13px">取消并全额退款</span>
        <span class="btn gray" style="height:36px;padding:0 18px;font-size:13px">强制关店</span>
      </div>
    </div>
    <div class="panel">
      <b>操作记录</b><span class="tiny muted" style="margin-left:10px">只增不改，保留 90 天</span>
      <table style="margin-top:8px"><thead><tr><th>时间</th><th>操作人</th><th>动作</th><th>变更前</th><th>变更后</th></tr></thead><tbody>{logs}</tbody></table>
    </div>
  </div>
  <div style="flex:.9">
    <div class="panel" style="margin-bottom:16px">
      <b>退款仲裁</b>
      <div class="tiny muted" style="margin-top:10px;line-height:1.8">接单后取消申请由商家处理；商家 24 小时未响应则自动同意退款。<br>强制退款金额不得超过实付金额，已完成订单不开放强制退款。</div>
      <div class="row between" style="margin-top:14px;font-size:13px"><span>退款金额</span><span class="price">32.00</span></div>
      <div class="row between" style="margin-top:8px;font-size:13px"><span>退款方式</span><span>原路退回钱包余额</span></div>
      <div class="row between" style="margin-top:8px;font-size:13px"><span>配送费</span><span class="muted">¥2.00 不退</span></div>
    </div>
    <div class="panel">
      <b>平台干预</b>
      <div class="tiny muted" style="margin-top:10px;line-height:1.8">强制关店后顾客端不可浏览；封禁账号后该用户四端均无法登录；所有干预动作写入操作记录并通知相关方。</div>
    </div>
  </div>
</div>'''
ui11 = desk('订单干预与仲裁', '订单干预', ui11_body, '平台运营 · 管理员', '平台侧')

screens = [
    ('UI-01_登录与角色入口.html', ui01),
    ('UI-02_顾客-店铺列表.html', ui02),
    ('UI-03_顾客-店铺详情与购物车.html', ui03),
    ('UI-04_顾客-确认订单.html', ui04),
    ('UI-05_顾客-订单跟踪.html', ui05),
    ('UI-06_商家-订单工作台.html', ui06),
    ('UI-07_商家-菜品与库存.html', ui07),
    ('UI-08_骑手-任务列表.html', ui08),
    ('UI-09_骑手-配送异常上报.html', ui09),
    ('UI-10_管理员-入驻审核.html', ui10),
    ('UI-11_管理员-订单干预与仲裁.html', ui11),
]

os.makedirs(HTML, exist_ok=True)
for name, content in screens:
    p = os.path.join(HTML, name)
    io.open(p, 'w', encoding='utf-8', newline='\n').write(content)
    print('written', name)
