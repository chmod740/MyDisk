# DjangoDisk 代码审查与修复报告

审查日期：2026-07-10

## 1. 审查范围

本次审查覆盖 `accounts`、`files`、`buckets`、`sharing`、项目配置、部署文件、主要模板和测试，重点检查：

- 认证、分享链接与 API Key 权限边界
- Markdown 预览、暗色模式和前端注入安全
- 文件上传、覆盖、软删除、级联删除和物理文件生命周期
- 存储配额与 `storage_used` 一致性
- 普通目录、桶目录和分享目录的 ZIP 下载
- API 一致性、路径校验、生产配置与 CI

## 2. 修复结果

### 高优先级

| 问题 | 状态 | 修复方式 |
|---|---|---|
| Markdown 存储型 XSS | 已修复 | 新增本地允许列表消毒模块，所有文件、桶和分享预览统一调用；Mermaid 启用 `strict` 安全级别 |
| 存储配额未执行 | 已修复 | 统一配额服务，事务内锁定用户，覆盖网页、API、桶、图片和 Markdown 编辑 |
| `storage_used` 失真 | 已修复 | `File`/`BucketFile` 信号按新旧差额更新，排除 `.keep`，新增 `recalculate_storage` 修复命令 |
| 删除后遗留物理文件 | 已修复 | 统一在事务提交后清理，覆盖硬删除、桶/用户级联删除和定时清理 |
| 软删除后分享仍可访问 | 已修复 | 软删除时撤销分享，访问时再次检查目标状态 |
| ZIP Slip | 已修复 | 统一规范化路径段与 POSIX 归档路径，拒绝 `..`、绝对路径、反斜杠和控制字符 |

### 中优先级

| 问题 | 状态 | 修复方式 |
|---|---|---|
| 私有桶分享无法下载 | 已修复 | 下载经由已验证的分享链接，不再复用桶所有者路由 |
| 登录开放重定向 | 已修复 | 使用 `url_has_allowed_host_and_scheme()` 校验 `next` |
| 覆盖上传先删旧文件 | 已修复 | 先写入新存储键并更新数据库，提交后再删旧对象；失败时保留旧文件 |
| ZIP 完整常驻内存 | 已修复 | 使用 `SpooledTemporaryFile` + `FileResponse`，大归档自动落盘并流式返回 |
| `.keep` 计入统计 | 已修复 | 桶文件数、容量、分享列表和用量均排除占位符 |
| 分享计数并发丢失 | 已修复 | 改用 `F('view_count') + 1` 原子更新 |
| 生产安全默认值 | 已修复 | 生产默认关闭 DEBUG，强制密钥与主机列表，启用 HTTPS/HSTS/Secure Cookie，Docker 秘密改为环境变量 |
| 前端 CDN 依赖 | 部分改进 | 安全消毒模块已本地化，其余大型前端库仍使用公共 CDN；离线环境需镜像静态资源 |

### 低优先级和可维护性

- `ShareLink` 已增加「file/folder/bucket 恰好一个非空」数据库约束，并兼容 Django 5/6 参数名。
- 桶 API 批量上传改为全部成功或全部失败，同名冲突统一返回 409，配额不足返回 413。
- 文件读取不再将内部异常和服务器路径返回给用户。
- 桶列表/API 使用聚合注解，避免每个桶额外查询数量和容量。
- `DATABASE_URL` 改用标准 URL 解析，支持编码凭据、IPv6 和 PostgreSQL 查询参数。
- 登出改为带 CSRF 的 POST；登录和分享密码默认限速。
- 分享文件夹 ZIP 与普通目录一致，递归包含子目录。
- 新增 GitHub Actions，分别运行单元测试与 Playwright E2E。

## 3. 测试补充

测试总数由 193 增加到 223，新覆盖：

- 外部/协议相对 `next` URL 被拒绝，GET 登出被拒绝，登录限速
- 已删除目标分享失效，分享密码限速
- 私有桶分享下载和跨桶越权拒绝
- 分享目录递归 ZIP，普通/桶 ZIP 流式响应和命名语义
- 网页、Files API 和 Bucket API 超配额拒绝与原子性
- API 上传/删除、大小变化和 `.keep` 的用量一致性
- 硬删除/桶级联删除的物理文件清理，事务回滚保留文件
- 覆盖上传存储失败时保留旧对象
- 非法桶路径被拒绝，`ShareLink` 恰好一个目标约束
- Markdown 预览统一使用本地消毒入口

验收结果：

```text
Found 223 test(s).
Ran 223 tests in 25.614s
OK
```

`python manage.py check`、`makemigrations --check --dry-run` 和生产环境 `check --deploy` 全部通过，`docker compose config --quiet` 通过。

## 4. 残余改进项

1. 将 Tailwind、HTMX、Marked、KaTeX、Mermaid、Highlight.js 和 Markdown CSS 收归到本地前端构建，生成带内容哈希的静态资源并启用严格 CSP。
2. 对超大 ZIP 增加总大小/文件数上限和并发下载限制；当前已避免归档完整常驻内存。
3. 如 API 规模继续扩大，可引入统一序列化/错误响应层（或 DRF），减少手写 JSON 解析和 method 检查。
