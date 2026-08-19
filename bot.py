import asyncio, ast, logging, operator as op, os, re, sqlite3, math, html, json
from datetime import datetime
from urllib.parse import quote_plus
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

BOT_TOKEN=os.getenv('BOT_TOKEN','').strip()
OPENAI_API_KEY=os.getenv('OPENAI_API_KEY','').strip()
MODEL=os.getenv('OPENAI_MODEL','gpt-5-mini').strip()
ADMIN_ID=int(os.getenv('ADMIN_ID','8960865438') or '8960865438')
DB_PATH=os.getenv('DB_PATH','novaai.db')
if not BOT_TOKEN: raise RuntimeError('BOT_TOKEN is missing')
logging.basicConfig(level=logging.INFO)
bot=Bot(BOT_TOKEN); dp=Dispatcher()

# ---------- database ----------
def db():
 c=sqlite3.connect(DB_PATH)
 c.execute('CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,username TEXT,name TEXT,messages_left INTEGER DEFAULT 50,created_at TEXT,banned INTEGER DEFAULT 0)')
 c.execute('CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,role TEXT,content TEXT,created_at TEXT)')
 c.commit(); return c

def ensure_user(m):
 c=db(); u=m.from_user
 c.execute('INSERT OR IGNORE INTO users(user_id,username,name,messages_left,created_at,banned) VALUES(?,?,?,?,?,0)',(u.id,u.username,u.full_name,50,datetime.utcnow().isoformat()))
 c.execute('UPDATE users SET username=?,name=? WHERE user_id=?',(u.username,u.full_name,u.id)); c.commit(); r=c.execute('SELECT messages_left FROM users WHERE user_id=?',(u.id,)).fetchone(); c.close(); return r[0]
def balance(uid):
 c=db(); r=c.execute('SELECT messages_left FROM users WHERE user_id=?',(uid,)).fetchone(); c.close(); return r[0] if r else 0
def consume(uid):
 c=db(); c.execute('UPDATE users SET messages_left=messages_left-1 WHERE user_id=? AND messages_left>0',(uid,)); c.commit(); c.close()
def banned(uid):
 c=db(); r=c.execute('SELECT banned FROM users WHERE user_id=?',(uid,)).fetchone(); c.close(); return bool(r and r[0])
def save(uid,role,text):
 c=db(); c.execute('INSERT INTO chats(user_id,role,content,created_at) VALUES(?,?,?,?)',(uid,role,text,datetime.utcnow().isoformat())); c.commit(); c.close()
def history(uid):
 c=db(); r=c.execute('SELECT role,content FROM chats WHERE user_id=? ORDER BY id DESC LIMIT 16',(uid,)).fetchall(); c.close(); return list(reversed(r))

# ---------- safe calculator ----------
BIN={ast.Add:op.add,ast.Sub:op.sub,ast.Mult:op.mul,ast.Div:op.truediv,ast.FloorDiv:op.floordiv,ast.Pow:op.pow,ast.Mod:op.mod}; UN={ast.USub:op.neg,ast.UAdd:op.pos}
def calc(expr):
 expr=expr.replace('^','**').replace('×','*').replace('÷','/')
 if len(expr)>150 or not re.fullmatch(r'[0-9+\-*/().%\s]+',expr): raise ValueError
 def walk(n):
  if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)) and not isinstance(n.value,bool): return n.value
  if isinstance(n,ast.UnaryOp) and type(n.op) in UN:return UN[type(n.op)](walk(n.operand))
  if isinstance(n,ast.BinOp) and type(n.op) in BIN:
   a,b=walk(n.left),walk(n.right)
   if isinstance(n.op,ast.Pow) and abs(b)>10: raise ValueError
   v=BIN[type(n.op)](a,b)
   if not math.isfinite(v) or abs(v)>10**15: raise ValueError
   return v
  raise ValueError
 return walk(ast.parse(expr,mode='eval').body)
def calc_request(t):
 m=re.match(r'^(?:احسب|حساب|حاسبة|calculate|calc)\s*[:：]?\s*(.+)$',t,re.I)
 if m:return m.group(1)
 if re.fullmatch(r'[0-9+\-*/().%^×÷\s]+',t) and any(x.isdigit() for x in t):return t

# ---------- free text tools ----------
def local_tool(t):
 x=t.strip(); l=x.lower(); e=calc_request(x)
 if e:
  try:
   v=calc(e); return f'🧮 النتيجة: {int(v) if isinstance(v,float) and v.is_integer() else v}'
  except ZeroDivisionError:return '❌ لا يمكن القسمة على صفر.'
  except:return '❌ عملية غير صحيحة. مثال: احسب 250*4+100'
 if re.match(r'^(اعكس|عكس)\b',x):
  s=x.split(':',1)[1].strip() if ':' in x else re.sub(r'^(اعكس|عكس)\s*','',x); return '🔄 النص المعكوس:\n'+s[::-1]
 m=re.match(r'^كرر\s+(.+?)\s+(\d+)$',x,re.S)
 if m:
  return '\n'.join(f'{i+1}️⃣ {m.group(1)}' for i in range(min(int(m.group(2)),30)))
 m=re.match(r'^(?:نظف|نظّف|تنظيف)\s*[:：]?\s*(.*)$',x,re.S)
 if m:return '🧹 النص المنظف:\n'+re.sub(r'\s+',' ',m.group(1)).strip()
 m=re.match(r'^(?:زخرف|زخرفة)\s*[:：]?\s*(.*)$',x,re.S)
 if m:
  s=m.group(1).strip();return f'✨ 『 {s} 』\n★ {s} ★\n• {s} •\n╰┈➤ {s}'
 m=re.match(r'^(?:عدد الكلمات|إحصائيات النص)\s*[:：]?\s*(.*)$',x,re.S)
 if m:
  s=m.group(1);return f'📊 الكلمات: {len(s.split())}\n🔤 الأحرف: {len(s)}\n📏 بدون مسافات: {len(re.sub(r"\s+", "", s))}'
 m=re.match(r'^(?:كبير|uppercase)\s*[:：]?\s*(.*)$',x,re.S)
 if m:return m.group(1).upper()
 m=re.match(r'^(?:صغير|lowercase)\s*[:：]?\s*(.*)$',x,re.S)
 if m:return m.group(1).lower()
 if l in ('مرحبا','هلا','hello','hi','السلام عليكم'):return '🤖 أهلاً بك! أنا NovaBiz AI.'
 if 'كيف حالك' in x or 'كيفك' in x:return 'بخير والحمد لله 🤖❤️'
 return None

# ---------- multi-source web retrieval ----------
async def web_sources(query):
 q=quote_plus(query); sources=[]
 timeout=aiohttp.ClientTimeout(total=12)
 async with aiohttp.ClientSession(timeout=timeout,headers={'User-Agent':'NovaBizAI/1.0'}) as s:
  # Wikipedia Arabic + English
  for lang in ('ar','en'):
   try:
    u=f'https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&format=json&utf8=1&srlimit=3'
    async with s.get(u) as r:
     if r.status==200:
      d=await r.json()
      for item in d.get('query',{}).get('search',[]):
       title=html.unescape(re.sub('<.*?>','',item.get('title',''))); snippet=html.unescape(re.sub('<.*?>','',item.get('snippet','')))
       sources.append({'title':title,'snippet':snippet,'url':f'https://{lang}.wikipedia.org/wiki/{quote_plus(item.get("title", ""))}'})
   except Exception: pass
  # DuckDuckGo instant answers: useful as a second independent source
  try:
   u=f'https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=0'
   async with s.get(u) as r:
    if r.status==200:
     d=await r.json()
     if d.get('AbstractText'): sources.append({'title':d.get('Heading','DuckDuckGo'),'snippet':d['AbstractText'],'url':d.get('AbstractURL','')})
     for z in d.get('RelatedTopics',[])[:4]:
      if isinstance(z,dict) and z.get('Text'): sources.append({'title':'DuckDuckGo','snippet':z['Text'],'url':z.get('FirstURL','')})
  except Exception: pass
 # unique and cap
 out=[]; seen=set()
 for x in sources:
  key=(x['title'],x['snippet'][:80])
  if key not in seen and x['snippet']:
   seen.add(key); out.append(x)
 return out[:8]

async def ai_answer(uid,text,sources):
 if not OPENAI_API_KEY:return None
 src='\n\n'.join(f"SOURCE {i+1}: {x['title']}\n{x['snippet']}\nURL: {x['url']}" for i,x in enumerate(sources))
 prompt=('أنت NovaBiz AI. أجب بدقة ووضوح بالعربية عند استخدام العربية. '
         'لا تخترع حقائق أو مصادر. إذا أُعطيت مصادر، قارن بينها واذكر عدم اليقين. '
         'إذا كان السؤال يحتاج معلومات حديثة فاستخدم المصادر المرفقة.\n\n'
         f'المصادر:\n{src or "لا توجد مصادر ويب"}')
 messages=[{'role':r,'content':c} for r,c in history(uid)]
 payload={'model':MODEL,'input':messages+[{'role':'user','content':text}], 'instructions':prompt}
 try:
  async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as s:
   async with s.post('https://api.openai.com/v1/responses',headers={'Authorization':f'Bearer {OPENAI_API_KEY}','Content-Type':'application/json'},json=payload) as r:
    d=await r.json()
    if r.status>=400: logging.error(d); return None
    return d.get('output_text')
 except Exception: logging.exception('AI request failed'); return None

def source_text(sources):
 if not sources:return ''
 return '\n\n📚 مصادر للاطلاع:\n'+'\n'.join(f'{i+1}. {x["title"]}\n{x["url"]}' for i,x in enumerate(sources[:5]) if x.get('url'))

# ---------- keyboards ----------
kb=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='🧠 اسأل Nova AI'),KeyboardButton(text='🔎 بحث موثوق')],[KeyboardButton(text='🧮 حاسبة'),KeyboardButton(text='✍️ كتابة')],[KeyboardButton(text='🔧 الأدوات المجانية'),KeyboardButton(text='💰 رصيدي')],[KeyboardButton(text='👤 حسابي'),KeyboardButton(text='ℹ️ المساعدة')]],resize_keyboard=True)
ak=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📊 الإحصائيات',callback_data='stats'),InlineKeyboardButton(text='👥 المستخدمون',callback_data='users')],[InlineKeyboardButton(text='💰 إضافة رصيد',callback_data='add'),InlineKeyboardButton(text='🚫 حظر',callback_data='ban')],[InlineKeyboardButton(text='📢 إذاعة',callback_data='broadcast'),InlineKeyboardButton(text='🔄 تحديث',callback_data='refresh')]])
def admin_id(uid):return uid==ADMIN_ID

# ---------- user handlers ----------
@dp.message(CommandStart())
async def start(m):
 ensure_user(m); await m.answer('🤖 أهلاً بك في *NovaBiz AI*\n\n🧠 مساعد ذكي + أدوات مجانية + بحث متعدد المصادر.\n🎁 رصيدك: 50 رسالة.',parse_mode='Markdown',reply_markup=kb)
@dp.message(Command('balance'))
@dp.message(F.text=='💰 رصيدي')
async def bal(m):ensure_user(m);await m.answer(f'💰 رصيدك الحالي: *{balance(m.from_user.id)}* رسالة',parse_mode='Markdown')
@dp.message(F.text=='👤 حسابي')
async def profile(m):
 ensure_user(m);u=m.from_user;await m.answer(f'👤 حسابك\n\nID: `{u.id}`\nالاسم: {u.full_name}\nالرصيد: {balance(u.id)}',parse_mode='Markdown')
@dp.message(F.text=='🧮 حاسبة')
async def calc_help(m):await m.answer('🧮 مثال: احسب 250*4+100')
@dp.message(F.text=='✍️ كتابة')
async def write_help(m):await m.answer('✍️ مثال: اكتب إعلان احترافي لمحلات القعود')
@dp.message(F.text=='🔎 بحث موثوق')
async def search_help(m):await m.answer('🔎 أرسل: بحث آخر أخبار اليمن\nوسأحاول جمع نتائج من أكثر من مصدر.')
@dp.message(F.text=='🔧 الأدوات المجانية')
async def tools(m):await m.answer('🔧 الأدوات:\n🧮 احسب 25*4\n🔄 اعكس: مرحبا\n🔁 كرر مرحبا 3\n🧹 نظف: هذا   نص\n✨ زخرف: NovaBiz\n📊 عدد الكلمات: هذا نص')
@dp.message(F.text=='ℹ️ المساعدة')
async def help_(m):await m.answer('🧠 اسألني أي سؤال.\n🔎 للأسئلة الحديثة اكتب «بحث» أو استخدم زر البحث.\n🧮 للحساب استخدم «احسب».\n👑 المدير: /admin')

# ---------- admin ----------
@dp.message(Command('admin'))
async def admin(m):
 if not admin_id(m.from_user.id):return
 await m.answer('👑 *لوحة تحكم NovaBiz AI*\n\nاختر:',parse_mode='Markdown',reply_markup=ak)
@dp.callback_query()
async def callbacks(q:CallbackQuery):
 if not admin_id(q.from_user.id):return await q.answer('غير مصرح',show_alert=True)
 if q.data=='stats':
  c=db();u=c.execute('SELECT COUNT(*) FROM users').fetchone()[0];msgs=c.execute('SELECT COUNT(*) FROM chats WHERE role="user"').fetchone()[0];ban=c.execute('SELECT COUNT(*) FROM users WHERE banned=1').fetchone()[0];c.close();await q.message.answer(f'📊 المستخدمون: {u}\n💬 أسئلة: {msgs}\n🚫 محظورون: {ban}')
 elif q.data=='users':
  c=db();rows=c.execute('SELECT user_id,name,messages_left,banned FROM users ORDER BY rowid DESC LIMIT 20').fetchall();c.close();txt='👥 المستخدمون\n\n'+'\n'.join(f'{r[1] or "بدون اسم"} | {r[0]} | 💰{r[2]}'+(' 🚫' if r[3] else '') for r in rows);await q.message.answer(txt[:4000])
 elif q.data=='add':await q.message.answer('💰 استخدم /add ID عدد')
 elif q.data=='ban':await q.message.answer('🚫 استخدم /ban ID أو /unban ID')
 elif q.data=='broadcast':await q.message.answer('📢 استخدم /broadcast نص الرسالة')
 elif q.data=='refresh':await q.message.edit_reply_markup(reply_markup=ak)
 await q.answer()
@dp.message(Command('add'))
async def add(m):
 if not admin_id(m.from_user.id):return
 p=m.text.split();
 if len(p)!=3 or not p[1].isdigit() or not p[2].lstrip('-').isdigit():return await m.answer('الاستخدام: /add ID عدد')
 c=db();c.execute('UPDATE users SET messages_left=messages_left+? WHERE user_id=?',(int(p[2]),int(p[1])));c.commit();c.close();await m.answer('✅ تم تحديث الرصيد.')
@dp.message(Command('ban'))
async def ban(m):
 if admin_id(m.from_user.id) and len(m.text.split())==2 and m.text.split()[1].isdigit():
  c=db();c.execute('UPDATE users SET banned=1 WHERE user_id=?',(int(m.text.split()[1]),));c.commit();c.close();await m.answer('🚫 تم الحظر.')
@dp.message(Command('unban'))
async def unban(m):
 if admin_id(m.from_user.id) and len(m.text.split())==2 and m.text.split()[1].isdigit():
  c=db();c.execute('UPDATE users SET banned=0 WHERE user_id=?',(int(m.text.split()[1]),));c.commit();c.close();await m.answer('✅ تم فك الحظر.')
@dp.message(Command('broadcast'))
async def broadcast(m):
 if not admin_id(m.from_user.id):return
 text=m.text.partition(' ')[2].strip()
 if not text:return await m.answer('الاستخدام: /broadcast رسالتك')
 c=db();ids=[r[0] for r in c.execute('SELECT user_id FROM users WHERE banned=0').fetchall()];c.close();ok=0
 for uid in ids:
  try:await bot.send_message(uid,'📢 رسالة من الإدارة:\n\n'+text);ok+=1
  except Exception:pass
  await asyncio.sleep(.04)
 await m.answer(f'📢 تم الإرسال إلى {ok} مستخدم.')

# ---------- main router ----------
@dp.message(F.text)
async def message_router(m):
 ensure_user(m)
 if banned(m.from_user.id):return await m.answer('🚫 حسابك محظور.')
 if m.text in ('🧠 اسأل Nova AI','🔎 بحث موثوق'):return await m.answer('أرسل سؤالك الآن.')
 local=local_tool(m.text)
 if local:return await m.answer(local)
 if balance(m.from_user.id)<=0:return await m.answer('❌ انتهى رصيدك. اطلب من المدير إضافة رصيد.')
 text=m.text.strip(); needs_search=bool(re.match(r'^(بحث|ابحث|آخر|اليوم|حالي|الآن|اخبار|أخبار)\b',text,re.I))
 sources=await web_sources(text) if needs_search else []
 await m.bot.send_chat_action(m.chat.id,'typing')
 ans=await ai_answer(m.from_user.id,text,sources)
 if ans:
  save(m.from_user.id,'user',text);save(m.from_user.id,'assistant',ans);consume(m.from_user.id);return await m.answer(ans+source_text(sources))
 if sources:
  body='🔎 نتائج متعددة المصادر:\n\n'+'\n\n'.join(f'• {x["title"]}\n{x["snippet"]}' for x in sources[:5]);return await m.answer(body+source_text(sources))
 await m.answer('🧠 لا يوجد محرك AI خارجي مفعّل حاليًا. الأدوات المجانية تعمل، ولتشغيل إجابات AI قوية أضف مفتاح مزود AI في GitHub Secrets.')

async def main():
 db().close(); logging.info('NovaBiz AI started | admin=%s',ADMIN_ID); await dp.start_polling(bot)
if __name__=='__main__':asyncio.run(main())
