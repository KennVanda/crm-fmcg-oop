"""
Unit test untuk crm_fmcg.py
Jalankan: python -m unittest test_crm_fmcg -v
(Colab: !python -m unittest test_crm_fmcg -v)
"""
import os
import tempfile
import unittest
from datetime import date

from crm_fmcg import (BeverageProduct, Company, CRMError, CRMSystem, Entity, FoodProduct, GoldCustomer,
                      HouseholdProduct, MemberCustomer, OutOfStockError, PersonalCareProduct,
                      Product, ProductNotSoldError, RegularCustomer, Transaction, VIPCustomer,
                      build_sample_data, load_csv, save_csv)

D = date(2026, 10, 1)


class BaseCase(unittest.TestCase):
    def setUp(self):
        Entity.reset_ids()
        Transaction.reset_ids()
        self.crm = CRMSystem()
        self.co_a = self.crm.register_company(Company("PT A", "Bandung"))
        self.co_b = self.crm.register_company(Company("PT B", "Jakarta"))
        self.mie = FoodProduct("Mi", 3_000, 100)
        self.air = BeverageProduct("Air", 4_000, 100)
        self.sabun = PersonalCareProduct("Sabun", 20_000, 50)
        self.co_a.add_product(self.mie)
        self.co_a.add_product(self.air)
        self.co_b.add_product(self.sabun)
        self.reg = self.crm.register_customer(RegularCustomer("Rina", "rina@mail.com", "Bandung"))
        self.mem = self.crm.register_customer(MemberCustomer("Mona", "mona@mail.com", "Bandung"))
        self.vip = self.crm.register_customer(VIPCustomer("Vino", "vino@mail.com", "Jakarta"))


class TestAbstractionAndEncapsulation(BaseCase):
    def test_abstract_class_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            Product("X", 1000)

    def test_ids_are_generated_per_class(self):
        self.assertEqual((self.co_a.id, self.mie.id, self.reg.id), ("CO001", "P001", "C001"))

    def test_invalid_price_and_email_rejected(self):
        with self.assertRaises(ValueError):
            self.mie.base_price = 0
        with self.assertRaises(ValueError):
            self.reg.email = "salah-email"

    def test_stock_cannot_be_overwritten_from_outside(self):
        self.mie.__stock = 999
        self.assertEqual(self.mie.stock, 100)

    def test_product_has_single_owner(self):
        with self.assertRaises(CRMError):
            self.co_b.add_product(self.mie)

    def test_transactions_are_read_only(self):
        self.assertIsInstance(self.reg.transactions, tuple)


class TestPolymorphism(BaseCase):
    def test_unit_price_differs_by_category(self):
        self.assertEqual(self.mie.unit_price(10), 2_850)    # makanan >=10: 5%
        self.assertEqual(self.air.unit_price(12), 3_600)    # minuman >=12: 10%
        self.assertEqual(self.sabun.unit_price(50), 20_000)  # perawatan: tanpa diskon
        self.assertAlmostEqual(HouseholdProduct("Deterjen", 10_000).unit_price(6), 9_300)

    def test_discount_rate_by_tier(self):
        rates = [c.discount_rate() for c in (self.reg, self.mem, self.vip)]
        self.assertEqual(rates, [0.0, 0.05, 0.10])

    def test_member_and_vip_points(self):
        self.mem.purchase(self.co_a, {self.air: 10}, D)   # 40.000 - 5% = 38.000 -> 3 poin
        self.vip.purchase(self.co_a, {self.air: 10}, D)   # 40.000 - 10% = 36.000 -> 3 x 2 = 6
        self.assertEqual((self.mem.points, self.vip.points), (3, 6))

    def test_gold_customer(self):
        gold = GoldCustomer("Gina", "gina@mail.com", "Bandung")
        self.assertIsInstance(gold, MemberCustomer)         # pewarisan
        self.assertEqual(gold.discount_rate(), 0.07)        # polymorphism
        trx = gold.purchase(self.co_a, {self.air: 5}, D)    # 5 x Rp4.000
        self.assertEqual(trx.total, 18_600)
        self.assertEqual(gold.points, 1)


class TestTransactions(BaseCase):
    def test_purchase_reduces_stock_and_records_both_sides(self):
        trx = self.reg.purchase(self.co_a, {self.mie: 4, self.air: 2}, D)
        self.assertEqual(trx.total, 4 * 3_000 + 2 * 4_000)
        self.assertEqual((self.mie.stock, self.air.stock), (96, 98))
        self.assertIn(trx, self.co_a.sales)
        self.assertIn(trx, self.reg.transactions)

    def test_out_of_stock_is_atomic(self):
        with self.assertRaises(OutOfStockError):
            self.reg.purchase(self.co_a, {self.mie: 5, self.air: 101}, D)
        self.assertEqual(self.mie.stock, 100)       # item pertama tidak ikut berkurang
        self.assertEqual(len(self.co_a.sales), 0)

    def test_product_not_sold_by_company(self):
        with self.assertRaises(ProductNotSoldError):
            self.reg.purchase(self.co_a, {self.sabun: 1}, D)


class TestAnalytics(BaseCase):
    def test_loyal_uses_share_of_wallet(self):
        for _ in range(5):
            self.reg.purchase(self.co_a, {self.mie: 1}, D)     # 15.000 di PT A
        self.reg.purchase(self.co_b, {self.sabun: 1}, D)       # 20.000 di PT B -> share A < 50%
        for _ in range(5):
            self.mem.purchase(self.co_a, {self.mie: 1}, D)
        loyal = [c for c, *_ in self.crm.loyal_customers(self.co_a)]
        self.assertEqual(loyal, [self.mem])

    def test_top_k_and_frequent_products(self):
        self.reg.purchase(self.co_b, {self.sabun: 2}, D)
        self.mem.purchase(self.co_a, {self.mie: 1}, D)
        self.mem.purchase(self.co_a, {self.mie: 1, self.air: 1}, D)
        self.assertEqual(self.crm.top_k_customers(1)[0][0], self.reg)
        self.assertEqual(self.crm.frequent_products(self.mem, 1)[0][0], self.mie)

    def test_churn_risk(self):
        self.reg.purchase(self.co_a, {self.mie: 1}, date(2026, 8, 1))
        self.mem.purchase(self.co_a, {self.mie: 1}, date(2026, 10, 20))
        risky = [c for c, *_ in self.crm.churn_risk(date(2026, 10, 31))]
        self.assertEqual(risky, [self.reg])


class TestUpdateAndRemove(BaseCase):
    def test_update_customer_and_price_are_validated(self):
        self.crm.update_customer(self.reg, email="rina.baru@mail.com", city="Cimahi")
        self.assertEqual((self.reg.email, self.reg.city), ("rina.baru@mail.com", "Cimahi"))
        self.crm.update_product_price(self.mie, 3_200)
        self.assertEqual(self.mie.base_price, 3_200)
        with self.assertRaises(ValueError):
            self.crm.update_customer(self.reg, email="tanpa-at")
        with self.assertRaises(ValueError):
            self.crm.update_product_price(self.mie, -1)

    def test_cannot_remove_data_with_history(self):
        self.reg.purchase(self.co_a, {self.mie: 1}, D)
        with self.assertRaises(CRMError):
            self.crm.remove_customer(self.reg)
        with self.assertRaises(CRMError):
            self.crm.remove_product(self.mie)

    def test_remove_unused_customer_and_product(self):
        self.crm.remove_customer(self.vip)
        self.crm.remove_product(self.sabun)
        self.assertNotIn(self.vip, self.crm.customers)
        self.assertNotIn(self.sabun, self.co_b.catalog)
        self.assertIsNone(self.sabun.company)


class TestCsvRoundTrip(unittest.TestCase):
    def test_save_then_load_gives_same_numbers(self):
        crm = build_sample_data()
        with tempfile.TemporaryDirectory() as folder:
            save_csv(crm, folder)
            self.assertEqual(len(os.listdir(folder)), 4)
            again = load_csv(folder)
        self.assertEqual(len(again.transactions), len(crm.transactions))
        self.assertEqual(round(sum(t.total for t in again.transactions)),
                         round(sum(t.total for t in crm.transactions)))
        self.assertEqual([p.stock for c in again.companies for p in c.catalog],
                         [p.stock for c in crm.companies for p in c.catalog])


if __name__ == "__main__":
    unittest.main(verbosity=2)
