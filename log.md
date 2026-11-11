创建好虚拟环境：
uv init --package --python 3.12

uv sync
自动用系统自带的python3.12

然后装上一堆依赖。
按照教程操作。


针对第一次push：

记得保存
git add -A
git status --short

git commit -m "feat: day1 项目骨架、配置与日志，/health 通过"
git log --oneline


cd E:\Steward
git remote add origin https://github.com/navelcf/Steward.git

我的分支现在叫 `master`，GitHub 现在默认叫 `main`。现在只有 1 个提交，改名最省事：
git branch -M main
git push -u origin main

以后提交
git status
git add
git commit -m "docs: 补充 git 流程、Milvus 官方 compose 方案与 PG18 部署记录"


类型	用在哪
feat:	加了新功能，比如 /health、新接口
fix:	修了 bug
docs:	只改文档、注释
chore:	配置、依赖、脚本、compose 这类杂活



对于docker的部分，安装wsl
wsl --install
wsl --status

可以先迁移到e盘（或者下载好再迁移）

下载windows脚本：
cd E:\milvus
Invoke-WebRequest https://raw.githubusercontent.com/milvus-io/milvus/refs/heads/master/scripts/standalone_embed.bat -OutFile standalone.bat


.\standalone.bat start
一般会卡在拉镜像

加速源结果
`https://docker.m.daocloud.io`
（DaoCloud）✅ 可用`https://docker.nju.edu.cn`
（南京大学）✅ 可用

1. 打开 Docker Desktop → 点右上角**齿轮（Settings）** → 左侧选 **Docker Engine**
2. 里面是一个 JSON 编辑框（大概率只有一个 `{}`），理论上应该为：

{
"builder": {
"gc": {
"defaultKeepStorage": "20GB",
"enabled": true
}
},
"experimental": false
}


3. 把它**整体替换**为：

{
  "builder": {
    "gc": {
      "defaultKeepStorage": "20GB",
      "enabled": true
    }
  },
  "experimental": false,
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.nju.edu.cn"
  ]
}

cd E:\milvus
.\standalone.bat start

docker ps

使用最新版本的attu，老版本老是出问题！
如果用过老版本，记得删掉
docker rm -f attu #这个只是删容器
docker rmi zilliz/attu:v3.0.0 #这个是彻底删了。

docker run -d --name attu -p 3000:3000 -v attu-data:/data zilliz/attu:latest

docker ps


到这里，**Milvus 部署这条线全部收尾**：

- ✅ Milvus Standalone 跑在 E 盘数据上（19530 端口，healthy）
- ✅ Docker 虚拟盘迁移 E 盘，C 盘不再被 Docker 吃空间
- ✅ Attu GUI 用 latest 版跑起来（[localhost:3000](https://localhost:3000)，连 `host.docker.internal:19530`）

但其实这里是有问题的

milvus 起不来了，启动几秒就停。

先看日志确认：
docker logs milvus-standalone 2>&1 | Select-String -Pattern "panic:" | Select-Object -Last 5

看到这个就是这次的问题：
panic: etcdserver: leader changed

原因是内置 etcd 太慢：启动要重放 61MB 的 WAL，选主要 1.4 到 1.9 秒。
etcd 默认选举超时只有 1 秒，超时就换 leader。
milvus 在选主完成前就发请求，被取消后直接 panic。



试过没用的：原生 Docker 卷、force-new-cluster、缩短选举超时。

最后有效的办法：etcd 单独起一个容器，milvus 连它。


重点：
milvus-standalone-docker-compose.yaml
这是官方的第二套方法，
理论上这个就是单独的容器了，就不会有之前的问题了。
下次应该按照这种方法安装。



这里有个前提要知道：docker run 的环境变量是建容器时写死的，改不了。
所以只能把 milvus 容器删了重建。数据在 E:\milvus\volumes\milvus，删容器不丢。

先备份 etcd 数据：
robocopy E:\milvus\volumes\milvus\etcd E:\milvus\volumes\milvus\etcd-backup-20261103 /E /R:0 /W:0

把数据搬到外部 etcd 的目录：
robocopy E:\milvus\volumes\milvus\etcd-backup-20261103 E:\milvus\etcd-data /E /R:0 /W:0

建网络：
docker network create milvus-net

拉 etcd 镜像（bitnami 和 quay 都拉不动，用阿里云这个）：
docker pull registry.cn-hangzhou.aliyuncs.com/google_containers/etcd:3.5.33-0

起 etcd：
docker run -d --name milvus-etcd --network milvus-net --restart unless-stopped -p 2379:2379 -p 2380:2380 -v E:\milvus\etcd-data:/etcd-data --entrypoint /usr/local/bin/etcd registry.cn-hangzhou.aliyuncs.com/google_containers/etcd:3.5.33-0 --name default --data-dir /etcd-data --listen-client-urls http://0.0.0.0:2379 --advertise-client-urls http://milvus-etcd:2379 --listen-peer-urls http://0.0.0.0:2380 --initial-advertise-peer-urls http://localhost:2380 --initial-cluster default=http://localhost:2380 --initial-cluster-state existing

两个参数不能漏：
--entrypoint /usr/local/bin/etcd 不写，容器起来就退。
--initial-cluster-state existing 数据目录里已经有 member，就必须用 existing。

等它健康（返回 is healthy 再往下）：
docker exec milvus-etcd etcdctl --endpoints=http://127.0.0.1:2379 endpoint health

删掉旧 milvus：
docker rm -f milvus-standalone

用外部 etcd 参数重建：
docker run -d --name milvus-standalone --security-opt seccomp:unconfined --network milvus-net -e ETCD_USE_EMBED=false -e ETCD_ENDPOINTS=milvus-etcd:2379 -e COMMON_STORAGETYPE=local -e DEPLOY_MODE=STANDALONE -v E:\milvus\volumes\milvus:/var/lib/milvus -v E:\milvus\user.yaml:/milvus/configs/user.yaml -p 19530:19530 -p 9091:9091 --health-cmd="curl -f http://localhost:9091/healthz" --health-interval=30s --health-start-period=90s --health-timeout=20s --health-retries=3 milvusdb/milvus:v3.0.5 milvus run standalone

和原来的比，动了四处：
1. ETCD_USE_EMBED 从 true 改成 false
2. 新加 ETCD_ENDPOINTS=milvus-etcd:2379
3. 删掉 ETCD_DATA_DIR 和 ETCD_CONFIG_PATH
4. 删掉 -p 2379:2379，端口给 etcd 容器了

验证：
docker ps
docker exec milvus-etcd etcdctl --endpoints=http://127.0.0.1:2379 endpoint health
curl http://localhost:9091/healthz

两个 Up、一个 healthy、一个 OK，就算成了。

再确认 milvus 真的在连外部 etcd：
docker inspect milvus-standalone --format "{{json .Config.Env}}"

输出里要有 ETCD_USE_EMBED=false 和 ETCD_ENDPOINTS=milvus-etcd:2379，不能有 ETCD_DATA_DIR。


另外，attu 连 milvus 要填 host.docker.internal:19530，填 localhost 连不上，因为 attu 不在 milvus-net 里。





然后，开始建造数据库postgresql
验证docker和wsl：

docker info --format '{{.ServerVersion}}'

我这里输出：

'29.9.2'

创建docker-compose.yml：

services:
  postgres:
    image: postgres:18
    container_name: steward-pg
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${DB_USER:-steward}
      POSTGRES_DB: ${DB_NAME:-steward}
      POSTGRES_PASSWORD: ${DB_PASSWORD:?DB_PASSWORD must be set in .env}
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql          # ← 到这一层，不是 /data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-steward} -d ${DB_NAME:-steward}"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  pgdata:



确认 5432 没被别人占
netstat -ano | Select-String ":5432"

确认 .env 里密码不是空的
Select-String -Path .env -Pattern '^DB_PASSWORD='


顺便确认这三行也在：
Select-String -Path .env -Pattern '^DB_(NAME|USER|PORT)='


验证 yaml 能被解析：
docker compose config


起容器：
docker compose up -d

这一步容易卡住：
先单独拉：
docker pull postgres:18

再起容器：
docker compose up -d

之后：
docker compose ps

预期（STATUS 要出现 healthy，刚起来可能显示 health: starting，等 5–10 秒再看）：

NAME         IMAGE                STATUS
steward-pg   postgres:18   Up 30 seconds (healthy)


验证能连：
docker compose exec postgres psql -U steward -d steward -c "SELECT 1;"

再确认宿主机端口通：
netstat -ano | Select-String ":5432"
理论输出：
TCP    127.0.0.1:5432         0.0.0.0:0              LISTENING       37008









































