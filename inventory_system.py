import sqlite3
import datetime
from typing import List, Dict, Optional
import json

class InventoryDatabase:
    def __init__(self, db_name: str = "inventory.db"):
        self.db_name = db_name
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Products table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                min_stock INTEGER DEFAULT 10,
                supplier TEXT,
                created_date TEXT,
                last_updated TEXT
            )
        ''')
        
        # Transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                transaction_type TEXT,
                quantity INTEGER,
                price REAL,
                date TEXT,
                notes TEXT,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute a query and return results"""
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if query.strip().upper().startswith('SELECT'):
            results = [dict(row) for row in cursor.fetchall()]
        else:
            conn.commit()
            results = cursor.rowcount
        
        conn.close()
        return results

class Product:
    def __init__(self, name: str, price: float, quantity: int, 
                 description: str = "", category: str = "", 
                 min_stock: int = 10, supplier: str = ""):
        self.name = name
        self.description = description
        self.category = category
        self.price = price
        self.quantity = quantity
        self.min_stock = min_stock
        self.supplier = supplier
        self.created_date = datetime.datetime.now().isoformat()
        self.last_updated = datetime.datetime.now().isoformat()

class InventoryManager:
    def __init__(self):
        self.db = InventoryDatabase()
    
    def add_product(self, product: Product) -> bool:
        """Add a new product to inventory"""
        try:
            query = '''
                INSERT INTO products (name, description, category, price, quantity, 
                                    min_stock, supplier, created_date, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
            params = (product.name, product.description, product.category,
                     product.price, product.quantity, product.min_stock,
                     product.supplier, product.created_date, product.last_updated)
            
            self.db.execute_query(query, params)
            self._log_transaction(self.get_product_by_name(product.name)['id'], 
                                'INITIAL_STOCK', product.quantity, product.price,
                                f"Initial stock for {product.name}")
            return True
        except Exception as e:
            print(f"Error adding product: {e}")
            return False
    
    def get_all_products(self) -> List[Dict]:
        """Get all products from inventory"""
        query = "SELECT * FROM products ORDER BY name"
        return self.db.execute_query(query)
    
    def get_product_by_id(self, product_id: int) -> Optional[Dict]:
        """Get product by ID"""
        query = "SELECT * FROM products WHERE id = ?"
        results = self.db.execute_query(query, (product_id,))
        return results[0] if results else None
    
    def get_product_by_name(self, name: str) -> Optional[Dict]:
        """Get product by name"""
        query = "SELECT * FROM products WHERE name = ?"
        results = self.db.execute_query(query, (name,))
        return results[0] if results else None
    
    def update_product(self, product_id: int, **kwargs) -> bool:
        """Update product information"""
        try:
            valid_fields = ['name', 'description', 'category', 'price', 
                           'quantity', 'min_stock', 'supplier']
            updates = []
            params = []
            
            for field, value in kwargs.items():
                if field in valid_fields:
                    updates.append(f"{field} = ?")
                    params.append(value)
            
            if not updates:
                return False
            
            updates.append("last_updated = ?")
            params.append(datetime.datetime.now().isoformat())
            params.append(product_id)
            
            query = f"UPDATE products SET {', '.join(updates)} WHERE id = ?"
            self.db.execute_query(query, tuple(params))
            return True
        except Exception as e:
            print(f"Error updating product: {e}")
            return False
    
    def delete_product(self, product_id: int) -> bool:
        """Delete a product from inventory"""
        try:
            query = "DELETE FROM products WHERE id = ?"
            self.db.execute_query(query, (product_id,))
            return True
        except Exception as e:
            print(f"Error deleting product: {e}")
            return False
    
    def add_stock(self, product_id: int, quantity: int, price: float = 0, notes: str = "") -> bool:
        """Add stock to existing product"""
        try:
            product = self.get_product_by_id(product_id)
            if not product:
                return False
            
            new_quantity = product['quantity'] + quantity
            self.update_product(product_id, quantity=new_quantity)
            self._log_transaction(product_id, 'STOCK_IN', quantity, price, notes)
            return True
        except Exception as e:
            print(f"Error adding stock: {e}")
            return False
    
    def remove_stock(self, product_id: int, quantity: int, price: float = 0, notes: str = "") -> bool:
        """Remove stock from existing product"""
        try:
            product = self.get_product_by_id(product_id)
            if not product:
                return False
            
            if product['quantity'] < quantity:
                print("Insufficient stock available!")
                return False
            
            new_quantity = product['quantity'] - quantity
            self.update_product(product_id, quantity=new_quantity)
            self._log_transaction(product_id, 'STOCK_OUT', quantity, price, notes)
            return True
        except Exception as e:
            print(f"Error removing stock: {e}")
            return False
    
    def get_low_stock_products(self) -> List[Dict]:
        """Get products with stock below minimum threshold"""
        query = "SELECT * FROM products WHERE quantity <= min_stock"
        return self.db.execute_query(query)
    
    def search_products(self, search_term: str) -> List[Dict]:
        """Search products by name, category, or supplier"""
        query = '''
            SELECT * FROM products 
            WHERE name LIKE ? OR category LIKE ? OR supplier LIKE ?
        '''
        term = f"%{search_term}%"
        return self.db.execute_query(query, (term, term, term))
    
    def get_transaction_history(self, product_id: int = None) -> List[Dict]:
        """Get transaction history for a product or all products"""
        if product_id:
            query = '''
                SELECT t.*, p.name as product_name 
                FROM transactions t 
                JOIN products p ON t.product_id = p.id 
                WHERE t.product_id = ? 
                ORDER BY t.date DESC
            '''
            return self.db.execute_query(query, (product_id,))
        else:
            query = '''
                SELECT t.*, p.name as product_name 
                FROM transactions t 
                JOIN products p ON t.product_id = p.id 
                ORDER BY t.date DESC
            '''
            return self.db.execute_query(query)
    
    def _log_transaction(self, product_id: int, transaction_type: str, 
                        quantity: int, price: float, notes: str = ""):
        """Log a transaction"""
        query = '''
            INSERT INTO transactions (product_id, transaction_type, quantity, price, date, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        '''
        params = (product_id, transaction_type, quantity, price,
                 datetime.datetime.now().isoformat(), notes)
        self.db.execute_query(query, params)
    
    def generate_inventory_report(self) -> Dict:
        """Generate comprehensive inventory report"""
        products = self.get_all_products()
        low_stock = self.get_low_stock_products()
        
        total_products = len(products)
        total_value = sum(p['price'] * p['quantity'] for p in products)
        categories = {}
        
        for product in products:
            category = product['category'] or 'Uncategorized'
            if category not in categories:
                categories[category] = {'count': 0, 'value': 0}
            categories[category]['count'] += 1
            categories[category]['value'] += product['price'] * product['quantity']
        
        return {
            'total_products': total_products,
            'total_inventory_value': round(total_value, 2),
            'low_stock_count': len(low_stock),
            'categories': categories,
            'low_stock_products': low_stock
        }

class InventoryUI:
    def __init__(self):
        self.manager = InventoryManager()
    
    def display_menu(self):
        """Display main menu"""
        print("\n" + "="*50)
        print("         INVENTORY MANAGEMENT SYSTEM")
        print("="*50)
        print("1. Add Product")
        print("2. View All Products")
        print("3. Search Products")
        print("4. Update Product")
        print("5. Delete Product")
        print("6. Add Stock")
        print("7. Remove Stock")
        print("8. View Low Stock Products")
        print("9. Transaction History")
        print("10. Generate Report")
        print("0. Exit")
        print("-"*50)
    
    def add_product_ui(self):
        """UI for adding a new product"""
        print("\n--- Add New Product ---")
        try:
            name = input("Product Name: ").strip()
            if not name:
                print("Product name is required!")
                return
            
            # Check if product already exists
            if self.manager.get_product_by_name(name):
                print("Product already exists!")
                return
            
            description = input("Description (optional): ").strip()
            category = input("Category (optional): ").strip()
            price = float(input("Price: $"))
            quantity = int(input("Initial Quantity: "))
            min_stock = int(input("Minimum Stock Level (default 10): ") or "10")
            supplier = input("Supplier (optional): ").strip()
            
            product = Product(name, price, quantity, description, category, min_stock, supplier)
            
            if self.manager.add_product(product):
                print(f"✓ Product '{name}' added successfully!")
            else:
                print("✗ Failed to add product!")
                
        except ValueError:
            print("✗ Invalid input! Please enter correct data types.")
        except Exception as e:
            print(f"✗ Error: {e}")
    
    def view_products_ui(self):
        """UI for viewing all products"""
        products = self.manager.get_all_products()
        
        if not products:
            print("\nNo products found in inventory.")
            return
        
        print(f"\n--- All Products ({len(products)} items) ---")
        print(f"{'ID':<4} {'Name':<20} {'Category':<15} {'Price':<10} {'Stock':<8} {'Min':<6}")
        print("-" * 70)
        
        for product in products:
            stock_status = "⚠️ LOW" if product['quantity'] <= product['min_stock'] else "✓"
            print(f"{product['id']:<4} {product['name'][:19]:<20} "
                  f"{(product['category'] or 'N/A')[:14]:<15} "
                  f"${product['price']:<9.2f} {product['quantity']:<8} "
                  f"{product['min_stock']:<6} {stock_status}")
    
    def search_products_ui(self):
        """UI for searching products"""
        search_term = input("\nEnter search term (name/category/supplier): ").strip()
        if not search_term:
            print("Search term cannot be empty!")
            return
        
        products = self.manager.search_products(search_term)
        
        if not products:
            print("No products found matching your search.")
            return
        
        print(f"\n--- Search Results ({len(products)} found) ---")
        for product in products:
            print(f"ID: {product['id']} | {product['name']} | "
                  f"Category: {product['category'] or 'N/A'} | "
                  f"Stock: {product['quantity']} | Price: ${product['price']:.2f}")
    
    def update_product_ui(self):
        """UI for updating product"""
        try:
            product_id = int(input("\nEnter Product ID to update: "))
            product = self.manager.get_product_by_id(product_id)
            
            if not product:
                print("Product not found!")
                return
            
            print(f"\nUpdating: {product['name']}")
            print("Press Enter to keep current value")
            
            updates = {}
            
            new_name = input(f"Name ({product['name']}): ").strip()
            if new_name: updates['name'] = new_name
            
            new_desc = input(f"Description ({product['description']}): ").strip()
            if new_desc: updates['description'] = new_desc
            
            new_category = input(f"Category ({product['category']}): ").strip()
            if new_category: updates['category'] = new_category
            
            new_price = input(f"Price (${product['price']}): ").strip()
            if new_price: updates['price'] = float(new_price)
            
            new_min_stock = input(f"Min Stock ({product['min_stock']}): ").strip()
            if new_min_stock: updates['min_stock'] = int(new_min_stock)
            
            new_supplier = input(f"Supplier ({product['supplier']}): ").strip()
            if new_supplier: updates['supplier'] = new_supplier
            
            if updates:
                if self.manager.update_product(product_id, **updates):
                    print("✓ Product updated successfully!")
                else:
                    print("✗ Failed to update product!")
            else:
                print("No changes made.")
                
        except ValueError:
            print("✗ Invalid input!")
        except Exception as e:
            print(f"✗ Error: {e}")
    
    def stock_operation_ui(self, operation: str):
        """UI for stock operations (add/remove)"""
        try:
            product_id = int(input(f"\nEnter Product ID to {operation} stock: "))
            product = self.manager.get_product_by_id(product_id)
            
            if not product:
                print("Product not found!")
                return
            
            print(f"Product: {product['name']} (Current Stock: {product['quantity']})")
            quantity = int(input(f"Quantity to {operation}: "))
            price = float(input("Unit Price (optional, 0 for none): ") or "0")
            notes = input("Notes (optional): ").strip()
            
            if operation == "add":
                success = self.manager.add_stock(product_id, quantity, price, notes)
            else:
                success = self.manager.remove_stock(product_id, quantity, price, notes)
            
            if success:
                updated_product = self.manager.get_product_by_id(product_id)
                print(f"✓ Stock updated! New quantity: {updated_product['quantity']}")
            else:
                print("✗ Failed to update stock!")
                
        except ValueError:
            print("✗ Invalid input!")
        except Exception as e:
            print(f"✗ Error: {e}")
    
    def view_low_stock_ui(self):
        """UI for viewing low stock products"""
        products = self.manager.get_low_stock_products()
        
        if not products:
            print("\n✓ All products are above minimum stock levels!")
            return
        
        print(f"\n⚠️  Low Stock Alert ({len(products)} products)")
        print(f"{'Name':<20} {'Current':<8} {'Minimum':<8} {'Shortage':<8}")
        print("-" * 50)
        
        for product in products:
            shortage = product['min_stock'] - product['quantity']
            print(f"{product['name'][:19]:<20} {product['quantity']:<8} "
                  f"{product['min_stock']:<8} {shortage:<8}")
    
    def view_transactions_ui(self):
        """UI for viewing transaction history"""
        print("\n1. All transactions")
        print("2. Specific product transactions")
        choice = input("Choice (1-2): ").strip()
        
        if choice == "1":
            transactions = self.manager.get_transaction_history()
        elif choice == "2":
            try:
                product_id = int(input("Enter Product ID: "))
                transactions = self.manager.get_transaction_history(product_id)
            except ValueError:
                print("Invalid Product ID!")
                return
        else:
            print("Invalid choice!")
            return
        
        if not transactions:
            print("No transactions found.")
            return
        
        print(f"\n--- Transaction History ({len(transactions)} records) ---")
        for t in transactions[:20]:  # Show last 20 transactions
            date = t['date'][:16]  # Format date
            print(f"{date} | {t['product_name']} | {t['transaction_type']} | "
                  f"Qty: {t['quantity']} | ${t['price']:.2f}")
            if t['notes']:
                print(f"  Notes: {t['notes']}")
    
    def generate_report_ui(self):
        """UI for generating inventory report"""
        print("\n--- Generating Inventory Report ---")
        report = self.manager.generate_inventory_report()
        
        print(f"\n📊 INVENTORY SUMMARY")
        print(f"{'='*40}")
        print(f"Total Products: {report['total_products']}")
        print(f"Total Inventory Value: ${report['total_inventory_value']:,.2f}")
        print(f"Low Stock Products: {report['low_stock_count']}")
        
        print(f"\n📁 BY CATEGORY:")
        for category, data in report['categories'].items():
            print(f"  {category}: {data['count']} items (${data['value']:,.2f})")
        
        if report['low_stock_products']:
            print(f"\n⚠️  LOW STOCK ALERTS:")
            for product in report['low_stock_products']:
                print(f"  • {product['name']}: {product['quantity']} units "
                      f"(min: {product['min_stock']})")
    
    def run(self):
        """Main application loop"""
        print("Welcome to Inventory Management System!")
        
        while True:
            self.display_menu()
            choice = input("Enter your choice (0-10): ").strip()
            
            if choice == "0":
                print("Thank you for using Inventory Management System!")
                break
            elif choice == "1":
                self.add_product_ui()
            elif choice == "2":
                self.view_products_ui()
            elif choice == "3":
                self.search_products_ui()
            elif choice == "4":
                self.update_product_ui()
            elif choice == "5":
                try:
                    product_id = int(input("\nEnter Product ID to delete: "))
                    if self.manager.delete_product(product_id):
                        print("✓ Product deleted successfully!")
                    else:
                        print("✗ Failed to delete product!")
                except ValueError:
                    print("✗ Invalid Product ID!")
            elif choice == "6":
                self.stock_operation_ui("add")
            elif choice == "7":
                self.stock_operation_ui("remove")
            elif choice == "8":
                self.view_low_stock_ui()
            elif choice == "9":
                self.view_transactions_ui()
            elif choice == "10":
                self.generate_report_ui()
            else:
                print("Invalid choice! Please try again.")
            
            input("\nPress Enter to continue...")

# Example usage and demo data
def add_sample_data(manager):
    """Add some sample products for testing"""
    sample_products = [
        Product("Laptop", 999.99, 15, "Gaming laptop", "Electronics", 5, "TechCorp"),
        Product("Office Chair", 299.50, 8, "Ergonomic office chair", "Furniture", 3, "FurniCorp"),
        Product("Coffee Beans", 12.99, 50, "Premium coffee beans", "Food", 20, "CoffeeCorp"),
        Product("Notebook", 3.99, 2, "A4 notebook", "Stationery", 10, "PaperCorp"),  # Low stock
    ]
    
    for product in sample_products:
        manager.add_product(product)

if __name__ == "__main__":
    # Initialize the system
    ui = InventoryUI()
    
    # Ask if user wants sample data
    print("Would you like to add sample data for testing? (y/n)")
    if input().lower().startswith('y'):
        add_sample_data(ui.manager)
        print("Sample data added!")
    
    # Run the application
    ui.run()