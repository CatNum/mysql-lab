#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_interview_lab.py

用途：为 MySQL 面试实验库 interview_lab 生成用户、商品、订单、订单明细、订单日志数据。

默认连接配置可以通过环境变量覆盖：
- MYSQL_HOST（数据库地址）
- MYSQL_PORT（数据库端口）
- MYSQL_USER（用户名）
- MYSQL_PASSWORD（密码）
- MYSQL_DATABASE（数据库名）

默认数据规模也可以通过环境变量覆盖：
- USER_COUNT（用户数量）
- PRODUCT_COUNT（商品数量）
- ORDER_COUNT（订单数量）
- ORDER_ITEM_COUNT（订单明细数量）
- ORDER_LOG_COUNT（订单日志数量）
- BATCH_SIZE（批量插入大小）
"""

import os
import random
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable, List, Sequence, Tuple

import pymysql


def env_int(name: str, default: int) -> int:
    """读取整数环境变量，用于覆盖数据规模或端口配置。"""
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": env_int("MYSQL_PORT", 3306),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "interview_lab"),
    "charset": "utf8mb4",
    "autocommit": False,
}

USER_COUNT = env_int("USER_COUNT", 50_000)
PRODUCT_COUNT = env_int("PRODUCT_COUNT", 5_000)
ORDER_COUNT = env_int("ORDER_COUNT", 500_000)
ORDER_ITEM_COUNT = env_int("ORDER_ITEM_COUNT", 1_200_000)
ORDER_LOG_COUNT = env_int("ORDER_LOG_COUNT", 1_800_000)
BATCH_SIZE = env_int("BATCH_SIZE", 2_000)

HOT_TENANT_ID = 1
HOT_USER_ID = 1001
NORMAL_USER_ID = 1002
HOT_PRODUCT_ID = 2001
NORMAL_PRODUCT_ID = 2002
PENDING_ORDER_ID = 3001
PAID_ORDER_ID = 3002
FIXED_EXPERIMENT_DAY = datetime(2026, 1, 1, 12, 0, 0)

CITIES = ["北京", "上海", "深圳", "杭州", "广州", "成都", "武汉", "南京", "西安", "苏州"]
CATEGORIES = ["手机", "电脑", "家电", "服饰", "美妆", "食品", "图书", "运动", "母婴", "数码配件"]

STATUS_WEIGHTS = [
    (0, 0.08),
    (1, 0.18),
    (2, 0.12),
    (3, 0.52),
    (4, 0.10),
]


def choose_weighted(pairs: Sequence[Tuple[int, float]]) -> int:
    """按权重选择状态，用于构造订单 status 倾斜分布。"""
    r = random.random()
    acc = 0.0
    for value, weight in pairs:
        acc += weight
        if r <= acc:
            return value
    return pairs[-1][0]


def random_created_at() -> datetime:
    """生成最近 180 天内的创建时间；最近 7 天权重更高，用于时间范围查询实验。"""
    now = datetime.now().replace(microsecond=0)
    if random.random() < 0.35:
        days = random.randint(0, 6)
    else:
        days = random.randint(7, 179)
    seconds = random.randint(0, 86399)
    return now - timedelta(days=days, seconds=seconds)


def pay_time_for(status: int, created_at: datetime):
    """根据订单状态生成支付时间。未支付和取消订单可能为空。"""
    if status in (1, 2, 3):
        return created_at + timedelta(minutes=random.randint(1, 60))
    return None


def connect():
    """创建数据库连接。"""
    return pymysql.connect(**DB_CONFIG)


def batch_insert(conn, sql: str, rows: Iterable[tuple], batch_size: int = BATCH_SIZE):
    """批量插入函数：按批次写入多行数据，避免单次 SQL 太大。"""
    buf: List[tuple] = []
    total = 0
    with conn.cursor() as cur:
        for row in rows:
            buf.append(row)
            if len(buf) >= batch_size:
                cur.executemany(sql, buf)
                conn.commit()
                total += len(buf)
                buf.clear()
        if buf:
            cur.executemany(sql, buf)
            conn.commit()
            total += len(buf)
    return total


def print_progress(name: str, done: int, total: int, started_at: float):
    """进度输出函数：显示当前生成到哪张表、多少行、耗时多少。"""
    elapsed = time.time() - started_at
    pct = done * 100 / total if total else 100
    print(f"[{name}] {done:,}/{total:,} ({pct:.1f}%) elapsed={elapsed:.1f}s")


def cleanup_data(conn):
    """清理旧数据。没有外键约束，但仍按依赖顺序删除。"""
    print("cleanup old data ...")
    with conn.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        for table in ["order_logs", "order_items", "orders", "products", "users"]:
            cur.execute(f"TRUNCATE TABLE {table}")
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()


def seed_fixed_records(conn):
    """固定实验数据初始化函数：保证热点用户、热点商品、固定订单存在。"""
    print("seed fixed records ...")
    now = datetime.now().replace(microsecond=0)
    fixed_created_at = FIXED_EXPERIMENT_DAY
    users = [
        (HOT_USER_ID, HOT_TENANT_ID, "hot_user_1001", "13800001001", "hot_user_1001@example.com", 1, 0, "杭州", 28, now, now),
        (NORMAL_USER_ID, 2, "normal_user_1002", "13800001002", "normal_user_1002@example.com", 1, 0, "上海", 30, now, now),
    ]
    products = [
        (HOT_PRODUCT_ID, HOT_TENANT_ID, "热点商品-库存锁实验", "数码配件", Decimal("199.00"), 100_000, 1, now),
        (NORMAL_PRODUCT_ID, 2, "普通商品-对照实验", "图书", Decimal("59.00"), 10_000, 1, now),
    ]
    orders = [
        (PENDING_ORDER_ID, HOT_TENANT_ID, "FIXED_PENDING_3001", HOT_USER_ID, Decimal("199.00"), 0, 0, 1, 0, None, fixed_created_at, now),
        (PAID_ORDER_ID, HOT_TENANT_ID, "FIXED_PAID_3002", HOT_USER_ID, Decimal("299.00"), 1, 1, 1, 0, fixed_created_at + timedelta(hours=1), fixed_created_at, now),
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO users(id, tenant_id, username, phone, email, status, deleted, city, age, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE username=VALUES(username), phone=VALUES(phone), email=VALUES(email), updated_at=VALUES(updated_at)
            """, users)
        cur.executemany(
            """
            INSERT INTO products(id, tenant_id, name, category, price, stock, status, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE name=VALUES(name), stock=VALUES(stock), status=VALUES(status)
            """, products)
        cur.executemany(
            """
            INSERT INTO orders(id, tenant_id, order_no, user_id, total_amount, status, pay_type, source, deleted, pay_time, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE status=VALUES(status), total_amount=VALUES(total_amount), updated_at=VALUES(updated_at)
            """, orders)
        cur.executemany(
            """
            INSERT INTO order_items(tenant_id, order_id, product_id, quantity, price, created_at)
            VALUES (%s,%s,%s,%s,%s,%s)
            """, [
                (HOT_TENANT_ID, PENDING_ORDER_ID, HOT_PRODUCT_ID, 1, Decimal("199.00"), fixed_created_at),
                (HOT_TENANT_ID, PAID_ORDER_ID, HOT_PRODUCT_ID, 1, Decimal("299.00"), fixed_created_at),
            ])
        cur.executemany(
            """
            INSERT INTO order_logs(tenant_id, order_id, old_status, new_status, remark, created_at)
            VALUES (%s,%s,%s,%s,%s,%s)
            """, [
                (HOT_TENANT_ID, PENDING_ORDER_ID, None, 0, "固定待支付订单创建", fixed_created_at),
                (HOT_TENANT_ID, PAID_ORDER_ID, None, 0, "固定已支付订单创建", fixed_created_at),
                (HOT_TENANT_ID, PAID_ORDER_ID, 0, 1, "固定已支付订单支付成功", fixed_created_at + timedelta(hours=1)),
            ])
    conn.commit()


def generate_users(conn):
    """生成用户数据函数：用于手机号、邮箱、城市年龄和软删除相关查询实验。"""
    sql = """
    INSERT INTO users(id, tenant_id, username, phone, email, status, deleted, city, age, created_at, updated_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """

    def rows():
        for user_id in range(1, USER_COUNT + 1):
            if user_id in (HOT_USER_ID, NORMAL_USER_ID):
                continue
            tenant_id = HOT_TENANT_ID if random.random() < 0.65 else random.randint(2, 20)
            created_at = random_created_at()
            yield (
                user_id,
                tenant_id,
                f"user_{user_id}",
                f"139{user_id:08d}",
                f"user_{user_id}@example.com",
                1 if random.random() < 0.95 else 0,
                0 if random.random() < 0.98 else 1,
                random.choice(CITIES),
                random.randint(18, 60),
                created_at,
                created_at,
            )

    total = batch_insert(conn, sql, rows())
    print(f"insert users: {total:,}")


def generate_products(conn):
    """生成商品数据函数：用于商品分类价格查询、库存扣减和锁冲突实验。"""
    sql = """
    INSERT INTO products(id, tenant_id, name, category, price, stock, status, created_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """

    def rows():
        for product_id in range(1, PRODUCT_COUNT + 1):
            if product_id in (HOT_PRODUCT_ID, NORMAL_PRODUCT_ID):
                continue
            tenant_id = HOT_TENANT_ID if random.random() < 0.65 else random.randint(2, 20)
            category = random.choice(CATEGORIES)
            price = Decimal(str(round(random.uniform(9.9, 3999.0), 2)))
            stock = random.randint(0, 20_000)
            status = 1 if random.random() < 0.92 else 0
            yield (product_id, tenant_id, f"商品_{product_id}", category, price, stock, status, random_created_at())

    total = batch_insert(conn, sql, rows())
    print(f"insert products: {total:,}")


def order_user_id(order_id: int) -> int:
    """构造热点用户与普通用户订单分布。"""
    if order_id <= 20_000:
        return HOT_USER_ID
    if 20_001 <= order_id <= 20_060:
        return NORMAL_USER_ID
    return random.randint(1, USER_COUNT)


def order_tenant_id(user_id: int) -> int:
    """构造热点租户：tenant_id=1 约占 60% 到 70%。"""
    if user_id == HOT_USER_ID or random.random() < 0.66:
        return HOT_TENANT_ID
    return random.randint(2, 20)


def generate_orders(conn):
    """生成订单数据函数：用于订单列表、深分页、事务可见性和慢查询实验。"""
    sql = """
    INSERT INTO orders(id, tenant_id, order_no, user_id, total_amount, status, pay_type, source, deleted, pay_time, created_at, updated_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    started = time.time()

    def rows():
        done = 0
        for order_id in range(1, ORDER_COUNT + 1):
            if order_id in (PENDING_ORDER_ID, PAID_ORDER_ID):
                continue
            user_id = order_user_id(order_id)
            tenant_id = order_tenant_id(user_id)
            status = choose_weighted(STATUS_WEIGHTS)
            created_at = random_created_at()
            amount = Decimal(str(round(random.uniform(20.0, 5000.0), 2)))
            pay_type = 0 if status == 0 else random.randint(1, 3)
            source = random.randint(1, 3)
            deleted = 0 if random.random() < 0.99 else 1
            done += 1
            if done % 50_000 == 0:
                print_progress("orders", done, ORDER_COUNT, started)
            yield (
                order_id,
                tenant_id,
                f"NO{order_id:012d}",
                user_id,
                amount,
                status,
                pay_type,
                source,
                deleted,
                pay_time_for(status, created_at),
                created_at,
                created_at,
            )

    total = batch_insert(conn, sql, rows())
    print(f"insert orders: {total:,}")


def random_order_id() -> int:
    """随机选择订单 ID。热点用户订单、固定订单和普通订单都会被覆盖到。"""
    r = random.random()
    if r < 0.08:
        return random.randint(1, 20_000)
    if r < 0.081:
        return random.choice([PENDING_ORDER_ID, PAID_ORDER_ID])
    oid = random.randint(1, ORDER_COUNT)
    if oid in (PENDING_ORDER_ID, PAID_ORDER_ID):
        return oid + 10
    return oid


def random_product_id() -> int:
    """构造热点商品：products.id=2001 出现在大量订单明细中。"""
    if random.random() < 0.18:
        return HOT_PRODUCT_ID
    pid = random.randint(1, PRODUCT_COUNT)
    if pid in (HOT_PRODUCT_ID, NORMAL_PRODUCT_ID):
        return NORMAL_PRODUCT_ID
    return pid


def generate_order_items(conn):
    """生成订单明细数据函数：用于 JOIN、商品销量聚合和热点商品慢查询实验。"""
    sql = """
    INSERT INTO order_items(tenant_id, order_id, product_id, quantity, price, created_at)
    VALUES (%s,%s,%s,%s,%s,%s)
    """
    started = time.time()

    def rows():
        for i in range(1, ORDER_ITEM_COUNT + 1):
            order_id = random_order_id()
            product_id = random_product_id()
            tenant_id = HOT_TENANT_ID if random.random() < 0.66 else random.randint(2, 20)
            quantity = random.randint(1, 5)
            price = Decimal(str(round(random.uniform(9.9, 3999.0), 2)))
            if i % 100_000 == 0:
                print_progress("order_items", i, ORDER_ITEM_COUNT, started)
            yield (tenant_id, order_id, product_id, quantity, price, random_created_at())

    total = batch_insert(conn, sql, rows())
    print(f"insert order_items: {total:,}")


def generate_order_logs(conn):
    """生成订单日志数据函数：用于日志深分页、时间范围扫描和归档类慢查询实验。"""
    sql = """
    INSERT INTO order_logs(tenant_id, order_id, old_status, new_status, remark, created_at)
    VALUES (%s,%s,%s,%s,%s,%s)
    """
    transitions = [(None, 0), (0, 1), (1, 2), (2, 3), (0, 4)]
    started = time.time()

    def rows():
        for i in range(1, ORDER_LOG_COUNT + 1):
            order_id = random_order_id()
            tenant_id = HOT_TENANT_ID if random.random() < 0.66 else random.randint(2, 20)
            old_status, new_status = random.choice(transitions)
            remark = f"状态从 {old_status} 变更为 {new_status}"
            if i % 100_000 == 0:
                print_progress("order_logs", i, ORDER_LOG_COUNT, started)
            yield (tenant_id, order_id, old_status, new_status, remark, random_created_at())

    total = batch_insert(conn, sql, rows())
    print(f"insert order_logs: {total:,}")


def verify_counts(conn):
    """数据校验函数：检查每张表行数和热点数据是否达标。"""
    checks = [
        ("users count", "SELECT COUNT(*) FROM users"),
        ("products count", "SELECT COUNT(*) FROM products"),
        ("orders count", "SELECT COUNT(*) FROM orders"),
        ("order_items count", "SELECT COUNT(*) FROM order_items"),
        ("order_logs count", "SELECT COUNT(*) FROM order_logs"),
        ("hot user orders", "SELECT COUNT(*) FROM orders WHERE user_id = 1001"),
        ("normal user orders", "SELECT COUNT(*) FROM orders WHERE user_id = 1002"),
        ("hot tenant orders", "SELECT COUNT(*) FROM orders WHERE tenant_id = 1"),
        ("hot product items", "SELECT COUNT(*) FROM order_items WHERE product_id = 2001"),
        ("fixed orders", "SELECT id, status, created_at FROM orders WHERE id IN (3001, 3002) ORDER BY id"),
        ("fixed products", "SELECT id, stock FROM products WHERE id IN (2001, 2002) ORDER BY id"),
        ("fixed experiment day", "SELECT COUNT(*) FROM orders WHERE user_id = 1001 AND created_at >= '2026-01-01 00:00:00' AND created_at < '2026-01-02 00:00:00'"),
    ]
    with conn.cursor() as cur:
        for name, sql in checks:
            cur.execute(sql)
            print(f"\n-- {name}")
            for row in cur.fetchall():
                print(row)


def print_config():
    """输出本次造数配置，便于执行前确认连接和规模。"""
    safe_config = dict(DB_CONFIG)
    safe_config["password"] = "***" if safe_config.get("password") else ""
    print("-- database config")
    print(safe_config)
    print("-- data size")
    print({
        "USER_COUNT": USER_COUNT,
        "PRODUCT_COUNT": PRODUCT_COUNT,
        "ORDER_COUNT": ORDER_COUNT,
        "ORDER_ITEM_COUNT": ORDER_ITEM_COUNT,
        "ORDER_LOG_COUNT": ORDER_LOG_COUNT,
        "BATCH_SIZE": BATCH_SIZE,
    })


def main():
    random.seed(20260621)
    print_config()
    conn = connect()
    try:
        cleanup_data(conn)
        seed_fixed_records(conn)
        generate_users(conn)
        generate_products(conn)
        generate_orders(conn)
        generate_order_items(conn)
        generate_order_logs(conn)
        verify_counts(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
