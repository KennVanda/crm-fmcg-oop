"""
CRM FMCG - Tugas Besar Dasar Pemrograman I (SI-102) - ITHB
Tema : "The companies sell products purchased by the customers"

Pilar OOP yang dipakai:
  1. Class & Object    : Company, Customer, Product, Transaction, CRMSystem, dll.
  2. Encapsulation     : atribut private (__stock, __transactions, ...) + @property + validasi setter
  3. Inheritance       : Entity -> Product -> FoodProduct/BeverageProduct/...
                         Entity -> Customer -> RegularCustomer -> MemberCustomer -> VIPCustomer
  4. Polymorphism      : unit_price(), discount_rate(), describe(), _on_purchase() di-override
  5. Abstraction       : Entity, Product, Customer adalah abstract class (ABC + @abstractmethod)

Cara menjalankan:
  python crm_fmcg.py          -> laporan lengkap + simpan grafik (charts/) dan data CSV (data/)
  python crm_fmcg.py --menu   -> menu interaktif (termasuk ubah/hapus data)
  python -m unittest test_crm_fmcg -v   -> unit test
  Google Colab (CRM_FMCG.ipynb): sel 1 simpan kode, sel 2 laporan, sel 3 menu, sel 4-5 unit test
"""
from __future__ import annotations

import os
import random
import sys
from abc import ABC, abstractmethod
import csv
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import date, timedelta


# =====================================================================
# 1. EXCEPTION KHUSUS
# =====================================================================
class CRMError(Exception):
    """Induk semua error di sistem CRM."""


class OutOfStockError(CRMError):
    """Stok produk tidak cukup."""


class ProductNotSoldError(CRMError):
    """Produk tidak dijual oleh perusahaan tersebut."""


# =====================================================================
# 2. ABSTRACTION: kelas dasar semua entitas
# =====================================================================
class Entity(ABC):
    """Kelas abstrak: setiap entitas punya ID unik dan nama."""

    PREFIX = "E"
    _counters: dict[str, int] = {}

    def __init__(self, name: str):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Nama tidak boleh kosong")
        n = Entity._counters.get(self.PREFIX, 0) + 1
        Entity._counters[self.PREFIX] = n
        self.__id = f"{self.PREFIX}{n:03d}"      # private: tidak bisa diubah dari luar
        self._name = name.strip()

    @classmethod
    def reset_ids(cls) -> None:
        """Mulai ulang penomoran ID (dipakai saat data dibangun ulang / dimuat dari CSV)."""
        Entity._counters.clear()

    @property
    def id(self) -> str:
        return self.__id

    @property
    def name(self) -> str:
        return self._name

    @abstractmethod
    def describe(self) -> str:
        """Setiap subclass WAJIB menjelaskan dirinya sendiri."""

    def __str__(self) -> str:
        return self.describe()

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.id}, {self.name!r})"


# =====================================================================
# 3. PRODUCT (FMCG) + turunannya
# =====================================================================
class Product(Entity):
    """Produk FMCG (abstrak). Harga per unit ditentukan oleh tiap kategori."""

    PREFIX = "P"
    CATEGORY = "Umum"

    def __init__(self, name: str, base_price: float, stock: int = 0):
        super().__init__(name)
        self.base_price = base_price          # lewat setter (validasi)
        self.__stock = 0
        self.restock(stock)
        self.__company: Company | None = None

    # ---- encapsulation: harga & stok dijaga lewat property ----
    @property
    def base_price(self) -> float:
        return self.__base_price

    @base_price.setter
    def base_price(self, value: float) -> None:
        if not isinstance(value, (int, float)) or value <= 0:
            raise ValueError("Harga harus angka positif")
        self.__base_price = float(value)

    @property
    def stock(self) -> int:
        return self.__stock

    def restock(self, qty: int) -> None:
        if not isinstance(qty, int) or qty < 0:
            raise ValueError("Jumlah restock harus bilangan bulat >= 0")
        self.__stock += qty

    def _reduce_stock(self, qty: int) -> None:
        """Hanya dipanggil oleh Company saat penjualan (protected)."""
        if qty > self.__stock:
            raise OutOfStockError(f"Stok {self.name} tinggal {self.__stock}, diminta {qty}")
        self.__stock -= qty

    @property
    def company(self) -> "Company | None":
        return self.__company

    def _release(self) -> None:
        """Dipanggil Company saat produk dihapus dari katalog."""
        self.__company = None

    def _assign_to(self, company: "Company") -> None:
        """Dipanggil Company.add_product(); satu produk hanya boleh punya satu pemilik."""
        if self.__company is not None and self.__company is not company:
            raise CRMError(f"{self.name} sudah dimiliki {self.__company.name}")
        self.__company = company

    @property
    def category(self) -> str:
        return self.CATEGORY

    # ---- abstraction + polymorphism ----
    @abstractmethod
    def unit_price(self, qty: int) -> float:
        """Harga per unit setelah aturan diskon grosir kategori ini."""

    def total_price(self, qty: int) -> float:
        return round(self.unit_price(qty) * qty)

    def describe(self) -> str:
        owner = self.__company.name if self.__company else "-"
        return (f"[{self.id}] {self.name:<24} {self.category:<12} "
                f"{rp(self.base_price):>9}  stok {self.stock:>4}  ({owner})")


class FoodProduct(Product):
    CATEGORY = "Makanan"

    def __init__(self, name, base_price, stock=0, shelf_life_days=180):
        super().__init__(name, base_price, stock)
        self.shelf_life_days = shelf_life_days

    def unit_price(self, qty: int) -> float:
        return self.base_price * (0.95 if qty >= 10 else 1.0)       # beli >=10: 5%


class BeverageProduct(Product):
    CATEGORY = "Minuman"

    def __init__(self, name, base_price, stock=0, volume_ml=250):
        super().__init__(name, base_price, stock)
        self.volume_ml = volume_ml

    def unit_price(self, qty: int) -> float:
        return self.base_price * (0.90 if qty >= 12 else 1.0)       # 1 karton (12): 10%


class PersonalCareProduct(Product):
    CATEGORY = "Perawatan"

    def unit_price(self, qty: int) -> float:
        return self.base_price                                       # tanpa diskon grosir


class HouseholdProduct(Product):
    CATEGORY = "Rumah Tangga"

    def unit_price(self, qty: int) -> float:
        return self.base_price * (0.93 if qty >= 6 else 1.0)        # beli >=6: 7%


# =====================================================================
# 4. CUSTOMER + turunannya
# =====================================================================
class Customer(Entity):
    """Pelanggan (abstrak). Tiap tier punya aturan diskon & reward sendiri."""

    PREFIX = "C"
    TIER = "-"

    def __init__(self, name: str, email: str, city: str):
        super().__init__(name)
        self.email = email
        self._city = city
        self.__transactions: list[Transaction] = []

    @property
    def email(self) -> str:
        return self.__email

    @email.setter
    def email(self, value: str) -> None:
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError(f"Email tidak valid: {value}")
        self.__email = value.lower()

    @property
    def city(self) -> str:
        return self._city

    @city.setter
    def city(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Kota tidak boleh kosong")
        self._city = value.strip()

    @property
    def tier(self) -> str:
        return self.TIER

    @property
    def transactions(self) -> tuple["Transaction", ...]:
        return tuple(self.__transactions)            # read-only dari luar

    @property
    def total_spending(self) -> float:
        return sum(t.total for t in self.__transactions)

    def _record(self, trx: "Transaction") -> None:
        self.__transactions.append(trx)
        self._on_purchase(trx)

    def purchase(self, company: "Company", items: dict[Product, int], when: date) -> "Transaction":
        """Customer membeli produk dari sebuah Company."""
        return company.sell(self, items, when)

    # ---- polymorphism ----
    @abstractmethod
    def discount_rate(self) -> float:
        """Persentase diskon transaksi untuk tier ini."""

    def _on_purchase(self, trx: "Transaction") -> None:
        """Hook setelah transaksi; default tidak melakukan apa-apa."""

    def describe(self) -> str:
        return (f"[{self.id}] {self.name:<20} {self.tier:<8} {self.city:<10} "
                f"belanja {rp(self.total_spending):>13}")


class RegularCustomer(Customer):
    TIER = "Regular"

    def discount_rate(self) -> float:
        return 0.0


class MemberCustomer(RegularCustomer):
    TIER = "Member"
    POINT_PER = 10_000          # 1 poin tiap Rp10.000
    POINT_MULTIPLIER = 1

    def __init__(self, name, email, city):
        super().__init__(name, email, city)
        self.__points = 0

    @property
    def points(self) -> int:
        return self.__points

    def discount_rate(self) -> float:
        return 0.05

    def _on_purchase(self, trx):
        self.__points += int(trx.total // self.POINT_PER) * self.POINT_MULTIPLIER

    def describe(self) -> str:
        return super().describe() + f"  poin {self.points}"


class VIPCustomer(MemberCustomer):
    TIER = "VIP"
    POINT_MULTIPLIER = 2

    def discount_rate(self) -> float:
        return 0.10


class GoldCustomer(MemberCustomer):
    TIER = "Gold"

    def discount_rate(self) -> float:
        return 0.07


# =====================================================================
# 5. TRANSACTION
# =====================================================================
class TransactionItem:
    __slots__ = ("product", "qty", "unit_price", "subtotal")

    def __init__(self, product: Product, qty: int):
        self.product = product
        self.qty = qty
        self.unit_price = product.unit_price(qty)       # polymorphism
        self.subtotal = round(self.unit_price * qty)


class Transaction:
    _seq = 0

    def __init__(self, company: "Company", customer: Customer, when: date):
        Transaction._seq += 1
        self.__id = f"T{Transaction._seq:05d}"
        self.__company = company
        self.__customer = customer
        self.__date = when
        self.__items: list[TransactionItem] = []
        self.__discount = 0.0

    @classmethod
    def reset_ids(cls) -> None:
        cls._seq = 0

    @property
    def id(self) -> str:
        return self.__id

    @property
    def company(self) -> "Company":
        return self.__company

    @property
    def customer(self) -> Customer:
        return self.__customer

    @property
    def date(self) -> date:
        return self.__date

    @property
    def items(self) -> tuple[TransactionItem, ...]:
        return tuple(self.__items)

    @property
    def discount(self) -> float:
        return self.__discount

    @property
    def gross(self) -> float:
        return sum(i.subtotal for i in self.__items)

    @property
    def total(self) -> float:
        return self.gross - self.__discount

    def _add_item(self, product: Product, qty: int) -> None:
        self.__items.append(TransactionItem(product, qty))

    def _finalize(self) -> None:
        self.__discount = round(self.gross * self.__customer.discount_rate())   # polymorphism

    def __str__(self):
        return (f"{self.id} {self.date} {self.customer.name} @ {self.company.name}: "
                f"{rp(self.total)} (diskon {rp(self.discount)})")


# =====================================================================
# 6. COMPANY
# =====================================================================
class Company(Entity):
    PREFIX = "CO"

    def __init__(self, name: str, city: str):
        super().__init__(name)
        self._city = city
        self.__catalog: dict[str, Product] = {}
        self.__sales: list[Transaction] = []

    @property
    def city(self) -> str:
        return self._city

    @property
    def catalog(self) -> tuple[Product, ...]:
        return tuple(self.__catalog.values())

    @property
    def sales(self) -> tuple[Transaction, ...]:
        return tuple(self.__sales)

    @property
    def revenue(self) -> float:
        return sum(t.total for t in self.__sales)

    def add_product(self, product: Product) -> None:
        product._assign_to(self)          # encapsulation: tidak menulis atribut milik Product
        self.__catalog[product.id] = product

    def _remove_product(self, product: Product) -> None:
        """Dipanggil CRMSystem.remove_product() setelah memastikan produk belum pernah terjual."""
        del self.__catalog[product.id]
        product._release()

    def sell(self, customer: Customer, items: dict[Product, int], when: date) -> Transaction:
        """Validasi dulu semua item (atomic), baru kurangi stok & catat."""
        if not items:
            raise ValueError("Keranjang kosong")
        for product, qty in items.items():
            if product.id not in self.__catalog:
                raise ProductNotSoldError(f"{product.name} tidak dijual oleh {self.name}")
            if not isinstance(qty, int) or qty <= 0:
                raise ValueError("Jumlah beli harus > 0")
            if product.stock < qty:
                raise OutOfStockError(f"Stok {product.name} tinggal {product.stock}, diminta {qty}")

        trx = Transaction(self, customer, when)
        for product, qty in items.items():
            product._reduce_stock(qty)
            trx._add_item(product, qty)
        trx._finalize()
        self.__sales.append(trx)
        customer._record(trx)
        return trx

    def describe(self) -> str:
        return (f"[{self.id}] {self.name:<22} {self._city:<10} {len(self.__catalog)} produk, "
                f"{len(self.__sales)} transaksi, omzet {rp(self.revenue)}")


# =====================================================================
# 7. CRM SYSTEM (analitik)
# =====================================================================
class CRMSystem:
    # Ambang batas bisnis dijadikan konstanta agar mudah diubah & dijelaskan di laporan
    LOYAL_MIN_TRX = 5        # minimal 5 transaksi (~1 kali per 2 bulan selama 10 bulan)
    LOYAL_MIN_SHARE = 0.50   # lebih dari separuh belanja ada di perusahaan tsb (mayoritas)
    CHURN_DAYS = 45          # 1,5x rata-rata jarak belanja pelanggan di data (~30 hari)

    def __init__(self):
        self.__companies: dict[str, Company] = {}
        self.__customers: dict[str, Customer] = {}

    # ---------- registrasi ----------
    def register_company(self, c: Company) -> Company:
        self.__companies[c.id] = c
        return c

    def register_customer(self, c: Customer) -> Customer:
        self.__customers[c.id] = c
        return c

    @property
    def companies(self) -> tuple[Company, ...]:
        return tuple(self.__companies.values())

    @property
    def customers(self) -> tuple[Customer, ...]:
        return tuple(self.__customers.values())

    @property
    def transactions(self) -> list[Transaction]:
        return [t for c in self.__companies.values() for t in c.sales]

    def find_company(self, key: str) -> Company | None:
        key = key.lower()
        return next((c for c in self.companies if key in (c.id.lower(), c.name.lower())), None)

    def find_customer(self, key: str) -> Customer | None:
        key = key.lower()
        return next((c for c in self.customers if key in (c.id.lower(), c.name.lower())), None)

    def find_product(self, key: str) -> Product | None:
        key = key.lower()
        return next((p for c in self.companies for p in c.catalog
                     if key in (p.id.lower(), p.name.lower())), None)

    # ---------- ubah & hapus data ----------
    def update_customer(self, customer: Customer, email: str | None = None,
                        city: str | None = None) -> Customer:
        """Ubah email/kota pelanggan; validasi tetap dijalankan oleh setter (encapsulation)."""
        if email is not None:
            customer.email = email
        if city is not None:
            customer.city = city
        return customer

    def update_product_price(self, product: Product, new_price: float) -> Product:
        product.base_price = new_price           # setter menolak harga <= 0
        return product

    def remove_customer(self, customer: Customer) -> None:
        """Pelanggan yang sudah bertransaksi tidak boleh dihapus agar riwayat penjualan tetap utuh."""
        if customer.transactions:
            raise CRMError(f"{customer.name} sudah memiliki {len(customer.transactions)} transaksi; "
                           "data tidak boleh dihapus")
        del self.__customers[customer.id]

    def remove_product(self, product: Product) -> None:
        """Produk yang pernah terjual tidak boleh dihapus agar nota lama tetap valid."""
        if any(it.product is product for t in self.transactions for it in t.items):
            raise CRMError(f"{product.name} sudah pernah terjual; data tidak boleh dihapus")
        product.company._remove_product(product)

    # ---------- [1] pelanggan loyal ----------
    def loyal_customers(self, company: Company, min_trx: int | None = None,
                        min_share: float | None = None):
        """Loyal = sering belanja di company ini (>= min_trx) DAN porsi belanjanya
        di company ini >= min_share dari total belanjanya (share of wallet)."""
        min_trx = self.LOYAL_MIN_TRX if min_trx is None else min_trx
        min_share = self.LOYAL_MIN_SHARE if min_share is None else min_share
        result = []
        for cust in self.customers:
            here = [t for t in cust.transactions if t.company is company]
            if not here or cust.total_spending == 0:
                continue
            share = sum(t.total for t in here) / cust.total_spending
            if len(here) >= min_trx and share >= min_share:
                result.append((cust, len(here), share, sum(t.total for t in here)))
        return sorted(result, key=lambda r: (-r[2], -r[1]))

    # ---------- [2] top-k spending ----------
    def top_k_customers(self, k: int = 5, company: Company | None = None):
        spend = defaultdict(float)
        for t in self.transactions:
            if company is None or t.company is company:
                spend[t.customer] += t.total
        return sorted(spend.items(), key=lambda kv: kv[1], reverse=True)[:k]

    # ---------- [3] produk yang sering dibeli customer ----------
    def frequent_products(self, customer: Customer, k: int = 3):
        """Diurutkan berdasarkan berapa kali produk muncul di transaksi, lalu total qty."""
        times, qty = Counter(), Counter()
        for t in customer.transactions:
            for it in t.items:
                times[it.product] += 1
                qty[it.product] += it.qty
        ranked = sorted(times, key=lambda p: (times[p], qty[p]), reverse=True)[:k]
        return [(p, p.company, times[p], qty[p]) for p in ranked]

    # ---------- [4] dan lainnya ----------
    def best_selling_products(self, k: int = 5, company: Company | None = None):
        qty, rev = Counter(), Counter()
        for t in self.transactions:
            if company is None or t.company is company:
                for it in t.items:
                    qty[it.product] += it.qty
                    rev[it.product] += it.subtotal
        return [(p, qty[p], rev[p]) for p, _ in qty.most_common(k)]

    def revenue_by_company(self) -> dict[str, float]:
        return {c.name: c.revenue for c in self.companies}

    def monthly_revenue(self) -> dict[str, dict[str, float]]:
        data: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for t in self.transactions:
            data[t.company.name][t.date.strftime("%Y-%m")] += t.total
        return {k: dict(sorted(v.items())) for k, v in data.items()}

    def category_share(self) -> dict[str, float]:
        rev = Counter()
        for t in self.transactions:
            for it in t.items:
                rev[it.product.category] += it.subtotal
        return dict(rev.most_common())

    def revenue_by_tier(self) -> dict[str, float]:
        rev = Counter()
        for c in self.customers:
            rev[c.tier] += c.total_spending
        return dict(rev)

    def average_basket(self, company: Company | None = None) -> float:
        trx = [t for t in self.transactions if company is None or t.company is company]
        return sum(t.total for t in trx) / len(trx) if trx else 0.0

    def churn_risk(self, today: date, days: int | None = None):
        """Pelanggan yang sudah >= `days` hari tidak belanja."""
        days = self.CHURN_DAYS if days is None else days
        out = []
        for c in self.customers:
            if c.transactions:
                last = max(t.date for t in c.transactions)
                gap = (today - last).days
                if gap >= days:
                    out.append((c, last, gap))
        return sorted(out, key=lambda r: -r[2])

    def rfm_segments(self, today: date) -> dict[Customer, tuple[str, int, int, float]]:
        """Segmentasi RFM sederhana (Recency, Frequency, Monetary), skor 1-3 per dimensi."""
        rows = []
        for c in self.customers:
            if c.transactions:
                rec = (today - max(t.date for t in c.transactions)).days
                rows.append((c, rec, len(c.transactions), c.total_spending))

        def score(values):
            """Skor tertil 1-3. bisect_left -> nilai yang sama selalu dapat skor yang sama."""
            ordered = sorted(values)
            n = len(ordered)
            return lambda v: 1 + min(2, bisect_left(ordered, v) * 3 // n)

        neg = score([-r[1] for r in rows])                  # recency: makin baru makin tinggi
        r_s = lambda rec: neg(-rec)
        f_s = score([r[2] for r in rows])
        m_s = score([r[3] for r in rows])
        out = {}
        for c, rec, freq, mon in rows:
            r, f, m = r_s(rec), f_s(freq), m_s(mon)
            if r == 3 and f + m >= 5:
                seg = "Champions"
            elif f + m >= 4 and r >= 2:
                seg = "Loyal"
            elif r == 1 and f + m >= 4:
                seg = "At Risk"
            elif r == 3:
                seg = "Promising"
            else:
                seg = "Need Attention"
            out[c] = (seg, rec, freq, mon)
        return out

    def recommend_products(self, customer: Customer, k: int = 3):
        """Rekomendasi: produk yang sering dibeli pelanggan lain yang punya
        produk favorit sama, tetapi belum pernah dibeli customer ini."""
        bought = {it.product for t in customer.transactions for it in t.items}
        score = Counter()
        for other in self.customers:
            if other is customer:
                continue
            other_bought = {it.product for t in other.transactions for it in t.items}
            overlap = len(bought & other_bought)
            for p in other_bought - bought:
                score[p] += overlap
        return [p for p, s in score.most_common(k) if s > 0]


# =====================================================================
# 7b. PENYIMPANAN CSV (persistensi data)
# =====================================================================
PRODUCT_CLASSES = {cls.__name__: cls for cls in
                   (FoodProduct, BeverageProduct, PersonalCareProduct, HouseholdProduct)}
CUSTOMER_CLASSES = {cls.__name__: cls for cls in (RegularCustomer, MemberCustomer, VIPCustomer,
                                                     GoldCustomer)}


def save_csv(crm: CRMSystem, folder: str = "data") -> list[str]:
    """Simpan seluruh data ke 4 file CSV agar tidak hilang saat program ditutup."""
    os.makedirs(folder, exist_ok=True)
    files = {
        "companies.csv": (["id", "name", "city"],
                          [[c.id, c.name, c.city] for c in crm.companies]),
        "products.csv": (["id", "company_id", "class", "name", "base_price", "stock"],
                         [[p.id, c.id, type(p).__name__, p.name, p.base_price, p.stock]
                          for c in crm.companies for p in c.catalog]),
        "customers.csv": (["id", "class", "name", "email", "city"],
                          [[c.id, type(c).__name__, c.name, c.email, c.city] for c in crm.customers]),
        "transactions.csv": (["trx_id", "date", "company_id", "customer_id", "product_id", "qty"],
                             [[t.id, t.date.isoformat(), t.company.id, t.customer.id, it.product.id, it.qty]
                              for t in sorted(crm.transactions, key=lambda t: t.id) for it in t.items]),
    }
    paths = []
    for name, (header, rows) in files.items():
        path = os.path.join(folder, name)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
        paths.append(path)
    return paths


def load_csv(folder: str = "data") -> CRMSystem:
    """Bangun ulang CRMSystem dari CSV. Transaksi diputar ulang lewat Company.sell(),
    jadi semua validasi & perhitungan diskon tetap berjalan seperti aslinya."""
    def read(name):
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            return list(csv.DictReader(f))

    Entity.reset_ids()
    Transaction.reset_ids()
    crm = CRMSystem()
    comp_map, prod_map, cust_map = {}, {}, {}
    sold = Counter()
    trx_rows = read("transactions.csv")
    for r in trx_rows:
        sold[r["product_id"]] += int(r["qty"])
    for r in read("companies.csv"):
        comp_map[r["id"]] = crm.register_company(Company(r["name"], r["city"]))
    for r in read("products.csv"):
        # stok awal = stok tersimpan + yang sudah terjual (karena transaksi akan diputar ulang)
        p = PRODUCT_CLASSES[r["class"]](r["name"], float(r["base_price"]),
                                        int(r["stock"]) + sold[r["id"]])
        comp_map[r["company_id"]].add_product(p)
        prod_map[r["id"]] = p
    for r in read("customers.csv"):
        cust_map[r["id"]] = crm.register_customer(
            CUSTOMER_CLASSES[r["class"]](r["name"], r["email"], r["city"]))
    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in trx_rows:
        grouped[r["trx_id"]].append(r)
    for rows in grouped.values():
        first = rows[0]
        items = {prod_map[r["product_id"]]: int(r["qty"]) for r in rows}
        cust_map[first["customer_id"]].purchase(comp_map[first["company_id"]], items,
                                                date.fromisoformat(first["date"]))
    return crm


# =====================================================================
# 8. DATA CONTOH (fiktif, seed tetap agar hasil selalu sama)
# =====================================================================
def build_sample_data(seed: int = 42) -> CRMSystem:
    rng = random.Random(seed)
    Entity.reset_ids()
    Transaction.reset_ids()
    crm = CRMSystem()

    sumber = crm.register_company(Company("PT Sumber Rasa Nusantara", "Bandung"))
    segar = crm.register_company(Company("PT Segar Jaya Abadi", "Jakarta"))
    bersih = crm.register_company(Company("PT Bersih Sentosa", "Surabaya"))

    catalog = {
        sumber: [FoodProduct("Mi Instan Goreng", 3_500, 2000),
                 FoodProduct("Biskuit Kelapa", 9_000, 1500),
                 FoodProduct("Kecap Manis 520ml", 21_000, 800),
                 BeverageProduct("Teh Melati Botol", 5_000, 2000, 350),
                 FoodProduct("Keripik Singkong", 12_000, 1000)],
        segar: [BeverageProduct("Air Mineral 600ml", 4_000, 3000, 600),
                BeverageProduct("Kopi Susu Kaleng", 8_500, 1500, 240),
                BeverageProduct("Jus Jeruk 1L", 18_000, 800, 1000),
                FoodProduct("Wafer Cokelat", 6_000, 1500),
                BeverageProduct("Minuman Isotonik", 7_500, 1500, 500)],
        bersih: [PersonalCareProduct("Sabun Mandi Cair", 25_000, 800),
                 PersonalCareProduct("Pasta Gigi 190g", 15_000, 1000),
                 PersonalCareProduct("Sampo Herbal", 32_000, 600),
                 HouseholdProduct("Deterjen Bubuk 1kg", 28_000, 900),
                 HouseholdProduct("Sabun Cuci Piring", 14_000, 1200)],
    }
    for comp, products in catalog.items():
        for p in products:
            comp.add_product(p)

    people = [
        ("Andi Saputra", "Bandung", VIPCustomer), ("Budi Santoso", "Jakarta", MemberCustomer),
        ("Citra Lestari", "Bandung", RegularCustomer), ("Dewi Anggraini", "Surabaya", VIPCustomer),
        ("Eko Prasetyo", "Bandung", MemberCustomer), ("Fajar Nugroho", "Jakarta", RegularCustomer),
        ("Gita Permata", "Bandung", MemberCustomer), ("Hendra Wijaya", "Surabaya", RegularCustomer),
        ("Indah Sari", "Jakarta", VIPCustomer), ("Joko Susilo", "Bandung", RegularCustomer),
        ("Kartika Putri", "Bandung", MemberCustomer), ("Lukas Hartono", "Jakarta", RegularCustomer),
        ("Maya Kusuma", "Surabaya", MemberCustomer), ("Nanda Pratama", "Bandung", RegularCustomer),
        ("Oki Firmansyah", "Jakarta", MemberCustomer), ("Putri Ayu", "Bandung", RegularCustomer),
        ("Rizky Ramadhan", "Surabaya", RegularCustomer), ("Sinta Maharani", "Jakarta", MemberCustomer),
        ("Teguh Wibowo", "Bandung", RegularCustomer), ("Vina Oktaviani", "Surabaya", MemberCustomer),
    ]
    companies = [sumber, segar, bersih]
    for name, city, cls in people:
        email = name.lower().replace(" ", ".") + "@mail.com"
        cust = crm.register_customer(cls(name, email, city))
        # tiap pelanggan punya perusahaan favorit -> pola loyalitas
        fav = rng.choice(companies)
        weights = [0.7 if c is fav else 0.15 for c in companies]
        # sebagian pelanggan berhenti belanja lebih awal -> pola churn
        last_day = date(2026, 10, 31) - timedelta(days=rng.choice([0, 0, 0, 10, 60, 100]))
        n_trx = rng.randint(4, 18) if cls is RegularCustomer else rng.randint(8, 22)
        start = date(2026, 1, 1)
        span = (last_day - start).days
        for _ in range(n_trx):
            comp = rng.choices(companies, weights)[0]
            picks = rng.sample(comp.catalog, rng.randint(1, 3))
            items = {p: rng.choice([1, 2, 3, 4, 6, 12]) for p in picks}
            when = start + timedelta(days=rng.randint(0, span))
            try:
                cust.purchase(comp, items, when)
            except CRMError:
                pass
    return crm


# =====================================================================
# 9. LAPORAN TEKS
# =====================================================================
def rp(x: float) -> str:
    return f"Rp{x:,.0f}".replace(",", ".")


def line(title: str = "") -> None:
    print("\n" + "=" * 78)
    if title:
        print(title)
        print("=" * 78)


def print_report(crm: CRMSystem, today: date, k: int = 5) -> None:
    line("PERUSAHAAN (polymorphism: describe())")
    for c in crm.companies:
        print(c)

    line("KATALOG PRODUK (polymorphism: unit_price() berbeda per kategori)")
    for c in crm.companies:
        for p in c.catalog:
            print(p, f"| harga/unit beli 12: {rp(p.unit_price(12))}")

    line(f"[2] TOP-{k} PELANGGAN BERDASARKAN TOTAL BELANJA (semua perusahaan)")
    for i, (c, s) in enumerate(crm.top_k_customers(k), 1):
        print(f"{i}. {c.name:<20} {c.tier:<8} {rp(s)}")
    for comp in crm.companies:
        print(f"\n   Top-3 di {comp.name}:")
        for i, (c, s) in enumerate(crm.top_k_customers(3, comp), 1):
            print(f"   {i}. {c.name:<20} {rp(s)}")

    line("[1] PELANGGAN LOYAL PER PERUSAHAAN (>=5 transaksi & share of wallet >=50%)")
    for comp in crm.companies:
        loyal = crm.loyal_customers(comp)
        print(f"\n{comp.name}: {len(loyal)} pelanggan loyal")
        for c, n, share, spent in loyal:
            print(f"   - {c.name:<20} {n:>2} trx  share {share:>5.1%}  {rp(spent)}")

    line("[3] PRODUK YANG PALING SERING DIBELI TIAP PELANGGAN (top-3)")
    for c in crm.customers:
        fav = ", ".join(f"{p.name} ({co.name.split()[1]}) x{n}" for p, co, n, q in crm.frequent_products(c))
        print(f"{c.name:<20} -> {fav}")

    line("[4a] PRODUK TERLARIS")
    for p, q, r in crm.best_selling_products(k):
        print(f"{p.name:<24} {p.company.name:<26} {q:>5} unit  {rp(r)}")

    line("[4b] OMZET & RATA-RATA KERANJANG PER PERUSAHAAN")
    for comp in crm.companies:
        print(f"{comp.name:<26} omzet {rp(comp.revenue):>15}  "
              f"rata-rata/trx {rp(crm.average_basket(comp))}")

    line("[4c] PORSI OMZET PER KATEGORI & PER TIER PELANGGAN")
    total = sum(crm.category_share().values())
    for cat, v in crm.category_share().items():
        print(f"{cat:<14} {rp(v):>15} ({v / total:.1%})")
    print()
    for tier, v in crm.revenue_by_tier().items():
        print(f"{tier:<14} {rp(v):>15}")

    line(f"[4d] RISIKO CHURN (tidak belanja >=45 hari per {today})")
    for c, last, gap in crm.churn_risk(today):
        print(f"{c.name:<20} terakhir {last}  ({gap} hari)")

    line("[4e] SEGMENTASI RFM")
    segs = crm.rfm_segments(today)
    for seg in ["Champions", "Loyal", "Promising", "At Risk", "Need Attention"]:
        names = [c.name for c, v in segs.items() if v[0] == seg]
        print(f"{seg:<15} ({len(names)}): {', '.join(names)}")

    line("[4f] REKOMENDASI PRODUK (contoh 3 pelanggan)")
    for c in crm.customers[:3]:
        print(f"{c.name:<20} -> {', '.join(p.name for p in crm.recommend_products(c))}")


def demo_validation(crm: CRMSystem) -> None:
    """Membuktikan encapsulation & validasi bekerja."""
    line("UJI VALIDASI (encapsulation & exception)")
    c = crm.customers[0]
    comp_a, comp_b = crm.companies[0], crm.companies[1]
    p = comp_a.catalog[0]
    tests = [
        ("Beli melebihi stok", lambda: c.purchase(comp_a, {p: p.stock + 1}, date(2026, 11, 1))),
        ("Beli produk yang tidak dijual company", lambda: c.purchase(comp_b, {p: 1}, date(2026, 11, 1))),
        ("Set harga negatif", lambda: setattr(p, "base_price", -500)),
        ("Email tidak valid", lambda: setattr(c, "email", "andi-at-mail")),
        ("Membuat object dari abstract class", lambda: Product("X", 1000)),
    ]
    for label, fn in tests:
        try:
            fn()
            print(f"[GAGAL]  {label}: tidak ditolak")
        except (CRMError, ValueError, TypeError) as e:
            print(f"[OK]     {label} -> ditolak: {type(e).__name__}: {e}")
    try:
        p.__stock = 999_999            # tidak mengubah stok asli (name mangling)
    except AttributeError:
        pass
    print(f"[OK]     Akses langsung p.__stock dari luar tidak mengubah stok asli: stok = {p.stock}")


# =====================================================================
# 10. GRAFIK
# =====================================================================
def save_charts(crm: CRMSystem, today: date, folder: str = "charts") -> list[str]:
    """Lima grafik dengan gaya seragam: data abu-abu, satu warna aksen pada temuan utama,
    judul berisi temuan, dan angka langsung di samping batang."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib belum terpasang: pip install matplotlib")
        return []
    os.makedirs(folder, exist_ok=True)
    ACCENT, MUTED, INK, SUB, GRID = "#2a78d6", "#c4c3bc", "#1f1f1d", "#6b6a63", "#e7e6e1"
    SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]          # tervalidasi aman untuk buta warna
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": SUB,
                         "xtick.color": SUB, "ytick.color": INK, "axes.spines.top": False,
                         "axes.spines.right": False})
    paths = []
    juta = lambda v: v / 1_000_000
    fmt = lambda v: f"Rp{v / 1e6:.2f} jt".replace(".", ",")

    def finish(fig, ax, title, subtitle, name):
        ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=INK, pad=24)
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9.5, color=SUB)
        fig.tight_layout()
        path = os.path.join(folder, name)
        fig.savefig(path, dpi=160)
        plt.close(fig)
        paths.append(path)

    def hbars(ax, labels, values, colors, texts):
        ys = range(len(labels))[::-1]
        ax.barh(list(ys), values, color=colors, height=0.62)
        ax.set_yticks(list(ys), labels)
        for y, v, t in zip(ys, values, texts):
            ax.text(v + max(values) * 0.01, y, t, va="center", fontsize=9, color=SUB)
        ax.set_xticks([]); ax.spines["bottom"].set_visible(False); ax.spines["left"].set_color(GRID)
        ax.set_xlim(0, max(values) * 1.25)

    # 1. top-10 pelanggan: Regular disorot
    top = crm.top_k_customers(10)
    n_reg = sum(1 for c, _ in top[:5] if c.tier == "Regular")
    fig, ax = plt.subplots(figsize=(8, 5))
    hbars(ax, [c.name for c, _ in top], [juta(s) for _, s in top],
          [ACCENT if c.tier == "Regular" else MUTED for c, _ in top],
          [f"{fmt(s)} \u00b7 {c.tier}" for c, s in top])
    finish(fig, ax, "Lima pembelanja terbesar semuanya pelanggan Regular" if n_reg == 5
           else f"{n_reg} dari 5 pembelanja terbesar adalah pelanggan Regular",
           "Total belanja Jan\u2013Okt 2026 \u00b7 biru = Regular (tanpa diskon/poin), abu-abu = Member/VIP",
           "1_top10_customers.png")

    # 2. omzet per perusahaan
    comps = sorted(crm.companies, key=lambda c: -c.revenue)
    total = sum(c.revenue for c in comps)
    fig, ax = plt.subplots(figsize=(8, 3))
    hbars(ax, [c.name for c in comps], [juta(c.revenue) for c in comps],
          [ACCENT] + [MUTED] * (len(comps) - 1),
          [f"{fmt(c.revenue)} ({c.revenue / total:.0%})" for c in comps])
    finish(fig, ax, f"{comps[0].name} menyumbang {comps[0].revenue / total:.0%} omzet",
           "Omzet Jan\u2013Okt 2026", "2_revenue_company.png")

    # 3. tren omzet bulanan
    monthly = crm.monthly_revenue()
    months = sorted({m for series in monthly.values() for m in series})
    names = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    if "2026-08" in months:
        i0 = months.index("2026-08")
        ax.axvspan(i0 - 0.5, len(months) - 0.5, color="#f1f0ec", zorder=0)
        ax.text(len(months) - 0.6, 3.85, "pelanggan mulai\nberhenti belanja", ha="right", va="top",
                fontsize=8.5, color=SUB)
    ordered = sorted(monthly.items(), key=lambda kv: -sum(kv[1].values()))
    label_y = []
    for color, (name, series) in zip(SERIES, ordered):
        ys = [juta(series.get(m, 0)) for m in months]
        ax.plot(range(len(months)), ys, color=color, lw=2, marker="o", ms=4)
        y = ys[-1]
        for other in label_y:                     # geser label agar tidak bertumpuk
            if abs(y - other) < 0.22:
                y = other - 0.22 if y <= other else other + 0.22
        label_y.append(y)
        ax.text(len(months) - 0.85, y, "  " + name.replace("PT ", ""), color=color, va="center",
                fontsize=9, fontweight="bold")
    ax.set_xticks(range(len(months)), [names[int(m[5:]) - 1] for m in months])
    ax.set_ylabel("Omzet (juta Rp)")
    ax.grid(axis="y", color=GRID); ax.set_ylim(0, 4)
    ax.set_xlim(-0.5, len(months) + 1.6)
    finish(fig, ax, "Omzet ketiga perusahaan turun tajam sejak Agustus", "Omzet bulanan 2026, juta Rp",
           "3_monthly_trend.png")

    # 4. porsi kategori (batang, bukan pie: lebih mudah dibandingkan)
    cat = crm.category_share()
    ctotal = sum(cat.values())
    top_cat = next(iter(cat))
    fig, ax = plt.subplots(figsize=(8, 3))
    hbars(ax, list(cat), [juta(v) for v in cat.values()], [ACCENT] + [MUTED] * (len(cat) - 1),
          [f"{fmt(v)} ({v / ctotal:.1%})".replace(".", ",", 1) for v in cat.values()])
    finish(fig, ax, f"{top_cat} menyumbang omzet terbesar ({cat[top_cat] / ctotal:.1%})".replace(".", ","),
           "Omzet per kategori FMCG, sebelum diskon tier", "4_category_share.png")

    # 5. segmentasi RFM
    segs = Counter(v[0] for v in crm.rfm_segments(today).values())
    order = ["Champions", "Loyal", "Promising", "At Risk", "Need Attention"]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    vals = [segs.get(s, 0) for s in order]
    ax.bar(order, vals, color=[ACCENT if s == "At Risk" else MUTED for s in order], width=0.6)
    for x, v in enumerate(vals):
        ax.text(x, v + 0.1, str(v), ha="center", color=INK, fontsize=10)
    ax.set_yticks([]); ax.spines["left"].set_visible(False); ax.tick_params(axis="x", colors=INK)
    finish(fig, ax, f"{segs.get('At Risk', 0)} pelanggan masuk segmen At Risk",
           f"Jumlah pelanggan per segmen RFM per {today.strftime('%d-%m-%Y')}", "5_rfm_segments.png")
    return paths


# =====================================================================
# 11. MENU INTERAKTIF
# =====================================================================
def interactive_menu(crm: CRMSystem, today: date) -> None:
    menu = """
=========== CRM FMCG ===========
1. Lihat perusahaan & katalog
2. Lihat pelanggan
3. Top-k pelanggan
4. Pelanggan loyal sebuah perusahaan
5. Produk favorit seorang pelanggan
6. Catat transaksi baru
7. Risiko churn & segmentasi RFM
8. Rekomendasi produk
9. Simpan data ke CSV
10. Ubah data pelanggan / harga produk
11. Hapus pelanggan / produk
0. Keluar"""
    while True:
        print(menu)
        choice = input("Pilih menu: ").strip()
        try:
            if choice == "1":
                for c in crm.companies:
                    print(c)
                    for p in c.catalog:
                        print("   ", p)
            elif choice == "2":
                for c in crm.customers:
                    print(c)
            elif choice == "3":
                k = int(input("k = ") or 5)
                for i, (c, s) in enumerate(crm.top_k_customers(k), 1):
                    print(f"{i}. {c.name} - {rp(s)}")
            elif choice == "4":
                comp = crm.find_company(input("ID/nama perusahaan (mis. CO001): "))
                if not comp:
                    print("Perusahaan tidak ditemukan"); continue
                for c, n, share, s in crm.loyal_customers(comp):
                    print(f"- {c.name}: {n} trx, share {share:.0%}, {rp(s)}")
            elif choice == "5":
                cust = crm.find_customer(input("ID/nama pelanggan (mis. C001): "))
                if not cust:
                    print("Pelanggan tidak ditemukan"); continue
                for p, co, n, q in crm.frequent_products(cust, 5):
                    print(f"- {p.name} dari {co.name}: {n}x transaksi, {q} unit")
            elif choice == "6":
                cust = crm.find_customer(input("ID pelanggan: "))
                comp = crm.find_company(input("ID perusahaan: "))
                if not cust or not comp:
                    print("Data tidak ditemukan"); continue
                for p in comp.catalog:
                    print("   ", p)
                cart: dict[Product, int] = {}
                print("Masukkan produk satu per satu (kosongkan ID untuk selesai).")
                while True:
                    pid = input("  ID produk: ").strip().lower()
                    if not pid:
                        break
                    prod = next((p for p in comp.catalog if p.id.lower() == pid), None)
                    if not prod:
                        print("  Produk tidak ada di katalog perusahaan ini"); continue
                    cart[prod] = cart.get(prod, 0) + int(input("  Jumlah: "))
                if not cart:
                    print("Keranjang kosong, transaksi dibatalkan"); continue
                trx = cust.purchase(comp, cart, today)
                for it in trx.items:
                    print(f"   {it.product.name:<24} {it.qty:>3} x {rp(it.unit_price)} = {rp(it.subtotal)}")
                print("Berhasil:", trx)
            elif choice == "7":
                for c, last, gap in crm.churn_risk(today):
                    print(f"[churn] {c.name}: {gap} hari")
                for c, (seg, *_r) in crm.rfm_segments(today).items():
                    print(f"[RFM] {c.name}: {seg}")
            elif choice == "8":
                cust = crm.find_customer(input("ID/nama pelanggan: "))
                if cust:
                    print(", ".join(p.name for p in crm.recommend_products(cust)) or "-")
            elif choice == "9":
                print("Tersimpan:", ", ".join(save_csv(crm)))
            elif choice == "10":
                what = input("Ubah (p)elanggan atau (h)arga produk? ").strip().lower()
                if what == "p":
                    cust = crm.find_customer(input("ID/nama pelanggan: "))
                    if not cust:
                        print("Pelanggan tidak ditemukan"); continue
                    email = input(f"Email baru [{cust.email}] (kosongkan jika tetap): ").strip() or None
                    city = input(f"Kota baru [{cust.city}] (kosongkan jika tetap): ").strip() or None
                    print("Berhasil:", crm.update_customer(cust, email, city))
                elif what == "h":
                    prod = crm.find_product(input("ID/nama produk: "))
                    if not prod:
                        print("Produk tidak ditemukan"); continue
                    print("Berhasil:", crm.update_product_price(prod, float(input("Harga baru: "))))
            elif choice == "11":
                what = input("Hapus (p)elanggan atau p(r)oduk? ").strip().lower()
                if what == "p":
                    cust = crm.find_customer(input("ID/nama pelanggan: "))
                    if cust:
                        crm.remove_customer(cust); print(f"{cust.name} dihapus")
                elif what == "r":
                    prod = crm.find_product(input("ID/nama produk: "))
                    if prod:
                        crm.remove_product(prod); print(f"{prod.name} dihapus")
            elif choice == "0":
                break
            else:
                print("Pilihan tidak dikenal")
        except (CRMError, ValueError) as e:
            print("Error:", e)


def main(argv: list[str] | None = None) -> CRMSystem:
    argv = sys.argv[1:] if argv is None else argv
    today = date(2026, 10, 31)
    crm = build_sample_data()
    if "--menu" in argv:
        interactive_menu(crm, today)
    else:
        print_report(crm, today)
        demo_validation(crm)
        line("Data disimpan ke CSV: " + ", ".join(save_csv(crm)))
        paths = save_charts(crm, today)
        if paths:
            line("Grafik tersimpan: " + ", ".join(paths))
    return crm


if __name__ == "__main__":
    main()
