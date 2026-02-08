# AI 智能客服填单系统

一个基于 RAG（检索增强生成）的智能客服系统。员工提问 → AI 自动回答 → 搞不定转人工 → 坐席处理 → 质检评分，完整闭环。

---

## 这个项目能干啥？

| 页面 | 功能 |
|------|------|
| **登录页** | 输入账号密码登录系统 |
| **员工端** | 员工发问题，AI 基于知识库自动回答；搞不定可以转人工 |
| **坐席端** | 人工客服接单、回复；有"智能助手"一键生成推荐回复 |
| **质检页** | 对已完结工单打分（准确性/规范性/解决度），形成闭环 |
| **知识库** | 上传 `.md` 文档，系统自动切片、向量化、生成 QA 对 |

### 工单生命周期

```
员工提问 → AI 对话中 → 转人工 → 坐席接单处理 → 结束工单 → 质检评分 → 归档
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3 + TypeScript + Vite |
| 后端 | Python + FastAPI + PyCore 框架 |
| 数据库 | SQLite（异步，开箱即用，无需安装） |
| AI 对话 | DeepSeek 大模型（意图识别 + 问答） |
| 向量化 | 阿里 Qwen text-embedding-v4 |
| 检索 | RAG：QA 库匹配 + 向量相似度搜索 |

---

## 快速开始（5 分钟跑起来）

### 前置要求

- **Python 3.9+**（终端输入 `python3 --version` 确认）
- **Node.js 16+**（终端输入 `node --version` 确认）
- **DeepSeek API Key**（去 https://platform.deepseek.com 注册获取）
- **阿里 DashScope API Key**（去 https://dashscope.console.aliyun.com 注册获取）

### 第一步：下载项目

```bash
git clone https://github.com/chichiqiqi/AI-customer-robot.git
cd AI-customer-robot
```

### 第二步：配置 API Key

打开 `backend/config/app.toml`，找到这两行，填入你的 Key：

```toml
[llm]
api_key = "sk-你的DeepSeek密钥"          # 填这里

[embedding]
api_key = "sk-你的DashScope密钥"          # 填这里
```

### 第三步：启动后端

```bash
# 安装 Python 依赖
cd backend
pip3 install -r requirements.txt

# 回到项目根目录
cd ..

# 创建数据库文件夹
mkdir -p data

# 启动后端服务
python3 -m uvicorn backend.src.main:app --host 0.0.0.0 --port 8000
```

看到这行就说明后端启动成功了：
```
Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 第四步：启动前端

**另开一个终端窗口**，运行：

```bash
cd frontend
npm install
npm run dev
```

看到这行就说明前端启动成功了：
```
Local: http://localhost:5173/
```

### 第五步：打开浏览器

访问 **http://localhost:5173**

- 账号：`admin`
- 密码：`123456`

---

## 使用流程

### 1. 先上传知识库

点击顶部导航 **"知识库"** → 上传一个 `.md` 文件 → 等待状态变为 ✅ ready

> 上传后系统会自动：切片文档 → 向量化存储 → 生成 QA 对

### 2. 员工发起咨询

点击 **"员工咨询"** → 点击「+ 发起新对话」→ 输入问题

> AI 会基于知识库内容回答。如果 AI 解决不了，点「转接人工」

### 3. 坐席处理工单

点击 **"坐席端"** → 看到待处理工单 → 点击「接单」

> 可以点「智能分析」获取推荐回复，也可以手动输入回复

### 4. 质检评分

点击 **"质检"** → 选择已完结工单 → 查看对话记录 → 打星评分 → 提交

---

## 项目结构

```
AI-customer-robot/
├── backend/                 # 后端代码
│   ├── config/app.toml      # ⭐ 配置文件（API Key 填这里）
│   ├── requirements.txt     # Python 依赖
│   └── src/
│       ├── main.py          # 后端入口
│       ├── api/routes/      # API 路由（auth/ticket/knowledge/qc）
│       ├── services/        # 业务逻辑（AI引擎/RAG/知识库/坐席助手）
│       ├── repositories/    # 数据库操作
│       └── db/models.py     # 数据库表定义
├── frontend/                # 前端代码
│   └── src/
│       ├── pages/           # 5 个页面（登录/员工/坐席/质检/知识库）
│       ├── services/        # API 调用封装
│       └── router/          # 路由配置
├── pycore/                  # PyCore 框架（内部框架，不用动）
└── data/                    # SQLite 数据库文件（自动生成）
```

---

## 外网访问（cpolar 内网穿透）

如果你想让别人（不在同一个 WiFi 下）也能访问你的系统，需要用 **cpolar** 做内网穿透。

### 什么是内网穿透？

你的电脑跑在家里/公司的局域网里，外面的人访问不了 `localhost`。cpolar 会给你一个公网地址（比如 `xxx.cpolar.top`），别人通过这个地址就能访问你本地的服务。

### 第一步：安装 cpolar

> 详细教程参考官方文档：https://www.cpolar.com/blog/macos-installation-cpolar

**Mac 用户**（通过 Homebrew 安装）：

```bash
# 1. 安装 cpolar
brew tap probezy/core && brew install cpolar

# 2. 认证（token 在 cpolar 官网获取）
cpolar authtoken 你的token

# 3. 安装并启动后台服务
sudo cpolar service install
sudo cpolar service start
```

安装完成后，打开浏览器访问 **http://localhost:9200**，用你的 cpolar 账号登录。

> 还没有 cpolar 账号？去 https://dashboard.cpolar.com/auth 免费注册一个。

### 第二步：创建隧道

1. 打开 cpolar 本地管理页面：http://localhost:9200/#/tunnels/list
2. 点击 **「创建隧道」**
3. 填写信息：

| 字段 | 填什么 |
|------|--------|
| 隧道名称 | 随便填，比如 `ai-customer` |
| 协议 | `http` |
| 本地地址 | `5173`（前端端口） |
| 域名类型 | 选「随机域名」（免费版） |

4. 点击 **「创建」**

### 第三步：配置前端允许外网域名

创建隧道后，cpolar 会分配一个公网地址，类似 `xxxxx.r22.cpolar.top`。

打开 `frontend/vite.config.ts`，把你的 cpolar 域名加进去：

```typescript
export default defineConfig({
  plugins: [vue()],
  server: {
    allowedHosts: ['你的域名.cpolar.top'],  // ← 改成你的 cpolar 域名
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

> **为什么要改这个？** Vite 开发服务器默认只允许 `localhost` 访问，加上 cpolar 域名后才能从外网打开页面。

### 第四步：重启前端 & 访问

```bash
# 在 frontend 目录下重启前端
cd frontend
npm run dev
```

然后把 cpolar 给你的公网地址（比如 `http://xxxxx.r22.cpolar.top`）发给别人，他们打开就能用了！

### cpolar 常见问题

**Q: 提示 "limited to simultaneous cpolar client sessions"**
免费版只能同时开 1 个隧道。去 http://localhost:9200/#/tunnels/list 关掉不用的隧道，或者在 https://dashboard.cpolar.com/status 查看在线状态。

**Q: 外网打开页面白屏 / Network Error**
检查三件事：
1. 后端是否在 8000 端口运行中
2. 前端是否在 5173 端口运行中
3. `vite.config.ts` 里的 `allowedHosts` 是否加了你的 cpolar 域名

**Q: 每次重启 cpolar 域名都变了**
免费版是随机域名，每次重启会变。付费版可以固定域名。域名变了记得同步更新 `vite.config.ts` 里的 `allowedHosts`。

---

## 常见问题

### Q: 启动后端报 "address already in use"
上一次的进程没关干净。运行：
```bash
lsof -ti :8000 | xargs kill -9
```
然后重新启动。

### Q: AI 回复说 "暂未找到相关信息"
知识库是空的。先去「知识库」页面上传一个 `.md` 文件。

### Q: 前端显示 "Network Error"
后端没启动。确保后端在 8000 端口运行中。

### Q: pip install 报错
试试用 `pip3` 代替 `pip`，或者加 `--user` 参数：
```bash
pip3 install -r requirements.txt --user
```

---

## 测试账号

| 账号 | 密码 |
|------|------|
| admin | 123456 |

---

## License

MIT
