本地生成密钥（PowerShell）

ssh-keygen -t rsa -b 4096 -m PEM -f "$env:USERPROFILE\\.ssh\\steward\_rsa"

\*\*中间会问 passphrase，直接回车三次跳过。\*\*



\*\*⚠️ 必须用 `-t rsa -m PEM`。\*\* Navicat 的 SSH 隧道只认 RSA 的 PEM 格式，ed25519 那种新格式它读不了。

跑完会生成两个文件：



C:\\Users\\程凡\\.ssh\\steward\_rsa        ← 私钥（Navicat 要用）

C:\\Users\\程凡\\.ssh\\steward\_rsa.pub    ← 公钥（要传到服务器）



\# 第 2 步：把公钥加到服务器



\*\*本地读出公钥内容：\*\*

Get-Content "$env:USERPROFILE\\.ssh\\steward\_rsa.pub"

\*\*复制输出的那串（`ssh-rsa AAAA...` 开头的一整行）。\*\*



\*\*然后在 Workbench 里跑：\*\*



mkdir -p \~/.ssh \&\& chmod 700 \~/.ssh

cat >> \~/.ssh/authorized\_keys

粘贴你复制的那一行，然后按 `Ctrl+D` 结束。



再补一句权限修正：

chmod 600 \~/.ssh/authorized\_keys



本地测试密钥能不能用

ssh -i "$env:USERPROFILE\\.ssh\\steward\_rsa" root@47.114.112.71



