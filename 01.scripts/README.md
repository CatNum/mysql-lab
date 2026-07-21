# MySQL 模拟实战造数脚本

## 一键执行

执行造数前，需要先手动执行 `00.模拟实战/00.建表脚本.md` 中的建表 SQL。该建表脚本会创建 `interview_lab` 数据库以及 `users`、`products`、`orders`、`order_items`、`order_logs` 五张表；造数脚本只负责清理这些表并写入实验数据。

在当前目录执行：

```bash
./run_seed.sh
```

## 修改数据库连接

默认连接：

- `MYSQL_HOST`（数据库地址）：`127.0.0.1`
- `MYSQL_PORT`（数据库端口）：`3306`
- `MYSQL_USER`（用户名）：`root`
- `MYSQL_PASSWORD`（密码）：空字符串
- `MYSQL_DATABASE`（数据库名）：`interview_lab`

可以用环境变量覆盖：

```bash
MYSQL_USER=root MYSQL_PASSWORD=your_password ./run_seed.sh
```

## 小规模试跑

第一次建议先小规模试跑：

```bash
USER_COUNT=5000 \
PRODUCT_COUNT=1000 \
ORDER_COUNT=50000 \
ORDER_ITEM_COUNT=120000 \
ORDER_LOG_COUNT=180000 \
./run_seed.sh
```

## 文件说明

- `seed_interview_lab.py`：造数主脚本，负责清理旧数据、插入固定实验数据、批量生成用户、商品、订单、订单明细、订单日志。
- `run_seed.sh`：一键执行脚本，负责创建虚拟环境、安装依赖、执行 Python 造数脚本。
- `requirements.txt`：Python 依赖清单。
