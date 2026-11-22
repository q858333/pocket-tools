# 多平台视频获取（本机网页）

在浏览器里粘贴链接，解析后勾选下载到本地。

## 支持站点

| 平台 | 链接示例 |
|------|----------|
| B 站 | `bilibili.com` / `b23.tv` |
| YouTube | `youtube.com` / `youtu.be` |
| 抖音 | `douyin.com` / `v.douyin.com` |
| X | `x.com` / `twitter.com` |

## 依赖

- Python 3.10+（`run.sh` 自动创建虚拟环境）
- **yt-dlp**：`brew install yt-dlp`
- **ffmpeg**：`brew install ffmpeg`
- **抖音 / X**：建议在所选浏览器中登录对应网站；B 站高清/会员需 B 站登录

打开网页后会自动检测上述工具；若有缺失，页面顶部会显示**安装命令与说明**。

## 启动

```bash
cd ~/Projects/pocket-tools/video-downloader
chmod +x run.sh
./run.sh
```

浏览器打开：**http://127.0.0.1:8765**

## 停止

在运行 `./run.sh` 的终端里按 **Ctrl + C** 即可结束。

或在任意终端执行：

```bash
cd ~/Projects/pocket-tools/video-downloader
./stop.sh
```

## 使用

1. 粘贴视频或合集链接
2. 选择清晰度与登录用的浏览器
3. 点击「获取视频列表」，勾选要下的条目
4. 点击「下载选中项」：单个视频在 `~/Downloads/video-web/`，多集在 `~/Downloads/video-web/<合集名>/`

## 说明

- 仅监听 `127.0.0.1`，不对外网开放
- 能否下载取决于站点权限、地域与浏览器 Cookie
- 请遵守各平台用户协议与版权规定，仅供个人学习使用