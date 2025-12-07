import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import hashlib
import datetime
import csv
import os

# =========================
# CONFIG & DATA
# =========================
DATE_FORMAT = "%Y-%m-%d"
DB_USERS = "users.db"
DB_BORROW = "borrow_records.db"


# =========================
# USER DATABASE
# =========================
class UserDatabase:
    def __init__(self, db_path=DB_USERS):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT
            )
        """)
        self.conn.commit()

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def add_user(self, username, password):
        try:
            self.conn.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                              (username, self.hash_password(password)))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def validate_user(self, username, password):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?",
                    (username, self.hash_password(password)))
        return cur.fetchone() is not None

    def close(self):
        self.conn.close()

# =========================
# BORROW DATABASE
# =========================
class BorrowDatabase:
    def __init__(self, db_path=DB_BORROW):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS borrow_records (
            id INTEGER PRIMARY KEY,
            member_type TEXT,
            reference_no TEXT,
            title TEXT,
            firstname TEXT,
            surname TEXT,
            mobile TEXT,
            address1 TEXT,
            address2 TEXT,
            postcode TEXT,
            book_id TEXT,
            book_title TEXT,
            author TEXT,
            date_borrowed TEXT,
            date_due TEXT,
            days_on_loan INTEGER,
            late_return_fine TEXT,
            selling_price TEXT,
            date_overdue TEXT,
            created_at TEXT
        )
        """)
        self.conn.commit()

    def _get_next_id(self):
        cur = self.conn.cursor()
        cur.execute("SELECT MAX(id) FROM borrow_records")
        max_id = cur.fetchone()[0]
        return 1 if max_id is None else max_id + 1

    def insert_record(self, record: dict):
        record_id = self._get_next_id()
        record["id"] = record_id
        record.setdefault("created_at", datetime.datetime.now().isoformat())
        cols = ", ".join(record.keys())
        placeholders = ", ".join("?" for _ in record)
        values = tuple(record.values())
        cur = self.conn.cursor()
        cur.execute(f"INSERT INTO borrow_records ({cols}) VALUES ({placeholders})", values)
        self.conn.commit()
        return record_id

    def fetch_all(self, where_clause=None, params=()):
        sql = "SELECT * FROM borrow_records"
        if where_clause:
            sql += " WHERE " + where_clause
        sql += " ORDER BY id ASC"
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

    def delete_by_id(self, record_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM borrow_records WHERE id = ?", (record_id,))
        cur.execute("UPDATE borrow_records SET id = id - 1 WHERE id > ?", (record_id,))
        self.conn.commit()
        return cur.rowcount

    def close(self):
        self.conn.close()

# =========================
# LOGIN FRAME
# =========================
class LoginFrame(ttk.Frame):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.db = UserDatabase()
        self.on_success = on_success
        self.username = tk.StringVar()
        self.password = tk.StringVar()

        ttk.Label(self, text="Username:").grid(row=0, column=0, pady=5)
        ttk.Entry(self, textvariable=self.username).grid(row=0, column=1, pady=5)
        ttk.Label(self, text="Password:").grid(row=1, column=0, pady=5)
        ttk.Entry(self, textvariable=self.password, show="*").grid(row=1, column=1, pady=5)

        ttk.Button(self, text="Login", command=self.login).grid(row=2, column=0, pady=15)
        ttk.Button(self, text="Sign Up", command=self.signup).grid(row=2, column=1, pady=15)

    def login(self):
        user = self.username.get().strip()
        pwd = self.password.get().strip()
        if not user or not pwd:
            messagebox.showwarning("Input Error", "Enter username and password")
            return
        if self.db.validate_user(user, pwd):
            self.db.close()
            self.destroy()
            self.on_success()
        else:
            messagebox.showerror("Login Failed", "Invalid username or password")

    def signup(self):
        user = self.username.get().strip()
        pwd = self.password.get().strip()
        if not user or not pwd:
            messagebox.showwarning("Input Error", "Enter username and password")
            return
        if self.db.add_user(user, pwd):
            messagebox.showinfo("Success", "Sign up successful! You can now login.")
        else:
            messagebox.showerror("Error", "Username already exists.")

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import datetime
import csv
import os

# =========================
# CONFIG & BOOK DATA (TOP)
# =========================
DB_FILENAME = "library_records.db"
DATE_FORMAT = "%Y-%m-%d"

# Keep the first three original sample books and then the African literature list
BOOK_LIST = [
    "Cinderella",
    "Game Design",
    "Ancient Rome",

    "Sundown at Dawn: A Liberian Odyssey",
    "The Rain and the Night",
    "Why Nobody Knows When He Will Die",
    "Things Fall Apart",
    "Arrow of God",
    "Nervous Conditions",
    "So Long a Letter",
    "The Beautyful Ones Are Not Yet Born",
    "Season of Migration to the North",
    "Petals of Blood",
    "Weep Not, Child",
    "The Palm-Wine Drinkard",
    "Purple Hibiscus",
    "The Joys of Motherhood"
]

# Mapping used to autofill Book ID, Author, Fine & Price
BOOK_MAPPING = {
    "Cinderella": {"book_id": "ISBN-101", "author": "Paul Parker", "late_return_fine": "2.99", "selling_price": "9.95", "days": 14},
    
    "Game Design": {"book_id": "ISBN-102", "author": "James Ford", "late_return_fine": "3.50", "selling_price": "12.95", "days": 12},
    
    "Ancient Rome": {"book_id": "ISBN-103", "author": "Julia White", "late_return_fine": "2.30", "selling_price": "10.99", "days": 10},

    "Sundown at Dawn: A Liberian Odyssey": {"book_id": "ISBN-104", "author": "Wilton G. S. Sankawulo", "late_return_fine": "3.00", "selling_price": "15.00", "days": 14},
    
    "The Rain and the Night": {"book_id": "ISBN-105", "author": "Wilton G. S. Sankawulo", "late_return_fine": "3.00", "selling_price": "14.00", "days": 14},
    
    "Why Nobody Knows When He Will Die and Other Stories": {"book_id": "ISBN-106", "author": "Wilton G. S. Sankawulo", "late_return_fine": "2.00", "selling_price": "14.00", "days": 14},
    
    "Things Fall Apart": {"book_id": "ISBN-107", "author": "Chinua Achebe", "late_return_fine": "3.50", "selling_price": "18.00", "days": 14},
    
    "Arrow of God": {"book_id": "ISBN-108", "author": "Chinua Achebe", "late_return_fine": "3.50", "selling_price": "17.00", "days": 14},
    
    "Nervous Conditions": {"book_id": "ISBN-109", "author": "Tsitsi Dangarembga", "late_return_fine": "3.00", "selling_price": "16.50", "days": 14},
    
    "So Long a Letter": {"book_id": "ISBN-1010", "author": "Mariama Bâ", "late_return_fine": "2.50", "selling_price": "14.50", "days": 14},
    
    "The Beautyful Ones Are Not Yet Born": {"book_id": "ISBN-1011", "author": "Ayi Kwei Armah", "late_return_fine": "3.50", "selling_price": "18.50", "days": 14},
    
    "Season of Migration to the North": {"book_id": "ISBN-1012", "author": "Tayeb Salih", "late_return_fine": "3.50", "selling_price": "19.00", "days": 14},
    
    "Petals of Blood": {"book_id": "ISBN-1013", "author": "Ngũgĩ wa Thiong’o", "late_return_fine": "4.00", "selling_price": "20.00", "days": 14},
    
    "Weep Not, Child": {"book_id": "ISBN-1014", "author": "Ngũgĩ wa Thiong’o", "late_return_fine": "3.50", "selling_price": "17.50", "days": 14},
    
    "The Palm-Wine Drinkard": {"book_id": "ISBN-1015", "author": "Amos Tutuola", "late_return_fine": "2.50", "selling_price": "13.50", "days": 14},
    
    "Purple Hibiscus": {"book_id": "ISBN-1016", "author": "Chimamanda Ngozi Adichie", "late_return_fine": "3.50", "selling_price": "19.00", "days": 14},
    
    "The Joys of Motherhood": {"book_id": "ISBN-1017", "author": "Buchi Emecheta", "late_return_fine": "3.00", "selling_price": "16.00", "days": 14}
}

# =========================
# DATABASE LAYER (SEPARATE)
# =========================
import sqlite3
import datetime

DB_FILENAME = "borrow_records.db"

class Database:
    """SQLite wrapper for borrow records with sequential IDs that shift on deletion."""
    def __init__(self, db_path=DB_FILENAME):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # For easier dict-like access
        self._create_tables()

    def _create_tables(self):
        sql = """
        CREATE TABLE IF NOT EXISTS borrow_records (
            id INTEGER PRIMARY KEY,
            member_type TEXT,
            reference_no TEXT,
            title TEXT,
            firstname TEXT,
            surname TEXT,
            mobile TEXT,
            address1 TEXT,
            address2 TEXT,
            postcode TEXT,
            book_id TEXT,
            book_title TEXT,
            author TEXT,
            date_borrowed TEXT,
            date_due TEXT,
            days_on_loan INTEGER,
            late_return_fine TEXT,
            selling_price TEXT,
            date_overdue TEXT,
            created_at TEXT
        );
        """
        self.conn.execute(sql)
        self.conn.commit()

    def _get_next_id(self):
        """Return the next ID (always max ID + 1)."""
        cur = self.conn.cursor()
        cur.execute("SELECT MAX(id) FROM borrow_records")
        max_id = cur.fetchone()[0]
        return 1 if max_id is None else max_id + 1

    def insert_record(self, record: dict):
        """Insert a new record at the end (highest ID)."""
        record_id = self._get_next_id()
        record["id"] = record_id
        if "created_at" not in record:
            record["created_at"] = datetime.datetime.now().isoformat()

        cols = ", ".join(record.keys())
        placeholders = ", ".join("?" for _ in record)
        values = tuple(record.values())
        cur = self.conn.cursor()
        cur.execute(f"INSERT INTO borrow_records ({cols}) VALUES ({placeholders})", values)
        self.conn.commit()
        return record_id

    def fetch_all(self, where_clause=None, params=()):
        sql = "SELECT * FROM borrow_records"
        if where_clause:
            sql += " WHERE " + where_clause
        sql += " ORDER BY id ASC"
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

    def delete_by_id(self, record_id):
        """Delete a record and shift all higher IDs down by 1 to maintain sequence."""
        cur = self.conn.cursor()

        # Delete the record
        cur.execute("DELETE FROM borrow_records WHERE id = ?", (record_id,))

        # Shift IDs down for all higher IDs
        cur.execute("""
            UPDATE borrow_records
            SET id = id - 1
            WHERE id > ?
        """, (record_id,))
        self.conn.commit()
        return cur.rowcount

    def close(self):
        self.conn.close()





# =========================
# APPLICATION UI & LOGIC
# =========================
class LibraryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Library Management System")
        self.root.geometry("1150x700")
        self.db = Database()

        # variables
        self.member_type = tk.StringVar()
        self.reference = tk.StringVar()
        self.title = tk.StringVar()
        self.firstname = tk.StringVar()
        self.surname = tk.StringVar()
        self.mobile = tk.StringVar()
        self.address1 = tk.StringVar()
        self.address2 = tk.StringVar()
        self.postcode = tk.StringVar()

        self.book_id = tk.StringVar()
        self.book_title = tk.StringVar()
        self.author = tk.StringVar()
        self.days_on_loan = tk.IntVar(value=14)
        self.late_return_fine = tk.StringVar()
        self.selling_price = tk.StringVar()
        self.date_borrowed = tk.StringVar()
        self.date_due = tk.StringVar()
        self.date_overdue = tk.StringVar()

        self._build_title()
        self._build_form()
        self._build_buttons()
        self._build_treeview()
        self._load_records()

        # ensure borrowed/due dates when user focuses window
        self.root.bind("<FocusIn>", lambda e: self._ensure_dates())

    def _build_title(self):
        lbl = ttk.Label(self.root, text="Library Management System", font=("Arial", 26, "bold"))
        lbl.pack(pady=8)

    def _build_form(self):
        frm = ttk.Frame(self.root, padding=10)
        frm.pack(fill="x", padx=12)

        # left (member)
        left = ttk.Frame(frm)
        left.grid(row=0, column=0, sticky="nw", padx=6)

        ttk.Label(left, text="Member Type:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(left, textvariable=self.member_type, values=["", "Student", "Lecturer", "Admin Staff"], width=20).grid(row=0, column=1, pady=2)

        ttk.Label(left, text="Reference No:").grid(row=1, column=0, sticky="w")
        ttk.Entry(left, textvariable=self.reference, width=24).grid(row=1, column=1, pady=2)

        ttk.Label(left, text="Title:").grid(row=2, column=0, sticky="w")
        ttk.Combobox(left, textvariable=self.title, values=["", "Miss", "Mrs", "Mr", "Dr", "Ms", "Cant"], width=20).grid(row=2, column=1, pady=2)

        ttk.Label(left, text="Firstname:").grid(row=3, column=0, sticky="w")
        ttk.Entry(left, textvariable=self.firstname, width=24).grid(row=3, column=1, pady=2)

        ttk.Label(left, text="Surname:").grid(row=4, column=0, sticky="w")
        ttk.Entry(left, textvariable=self.surname, width=24).grid(row=4, column=1, pady=2)

        ttk.Label(left, text="Address 1:").grid(row=5, column=0, sticky="w")
        ttk.Entry(left, textvariable=self.address1, width=24).grid(row=5, column=1, pady=2)

        ttk.Label(left, text="Address 2:").grid(row=6, column=0, sticky="w")
        ttk.Entry(left, textvariable=self.address2, width=24).grid(row=6, column=1, pady=2)

        ttk.Label(left, text="Post Code:").grid(row=7, column=0, sticky="w")
        ttk.Entry(left, textvariable=self.postcode, width=24).grid(row=7, column=1, pady=2)

        ttk.Label(left, text="Mobile No:").grid(row=8, column=0, sticky="w")
        ttk.Entry(left, textvariable=self.mobile, width=24).grid(row=8, column=1, pady=2)

        # right (book)
        right = ttk.Frame(frm)
        right.grid(row=0, column=1, sticky="nw", padx=18)

        ttk.Label(right, text="Book ID:").grid(row=0, column=0, sticky="w")
        ttk.Entry(right, textvariable=self.book_id, width=30).grid(row=0, column=1, pady=2)

        ttk.Label(right, text="Book Title:").grid(row=1, column=0, sticky="w")
        ttk.Entry(right, textvariable=self.book_title, width=30).grid(row=1, column=1, pady=2)

        ttk.Label(right, text="Author:").grid(row=2, column=0, sticky="w")
        ttk.Entry(right, textvariable=self.author, width=30).grid(row=2, column=1, pady=2)

        ttk.Label(right, text="Days On Loan:").grid(row=3, column=0, sticky="w")
        ttk.Spinbox(right, from_=1, to=365, textvariable=self.days_on_loan, width=7).grid(row=3, column=1, sticky="w", pady=2)

        ttk.Label(right, text="Late Return Fine:").grid(row=4, column=0, sticky="w")
        ttk.Entry(right, textvariable=self.late_return_fine, width=15).grid(row=4, column=1, sticky="w", pady=2)

        ttk.Label(right, text="Selling Price:").grid(row=5, column=0, sticky="w")
        ttk.Entry(right, textvariable=self.selling_price, width=15).grid(row=5, column=1, sticky="w", pady=2)

        ttk.Label(right, text="Date Borrowed:").grid(row=6, column=0, sticky="w")
        ttk.Entry(right, textvariable=self.date_borrowed, width=20).grid(row=6, column=1, sticky="w", pady=2)

        ttk.Label(right, text="Date Due:").grid(row=7, column=0, sticky="w")
        ttk.Entry(right, textvariable=self.date_due, width=20).grid(row=7, column=1, sticky="w", pady=2)

        ttk.Label(right, text="Date Over Due:").grid(row=8, column=0, sticky="w")
        ttk.Entry(right, textvariable=self.date_overdue, width=20).grid(row=8, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Tip: Select a book in the list (below) to auto-fill values.", foreground="gray").grid(row=1, column=0, columnspan=2, sticky="w", pady=(6,0))

        # Quick book list on right for selection/autofill
        book_frame = ttk.Frame(self.root, padding=6)
        book_frame.place(relx=0.78, rely=0.15)
        ttk.Label(book_frame, text="Books (click to auto-fill)").pack(anchor="w")
        self.book_listbox = tk.Listbox(book_frame, height=14, width=36)
        for b in BOOK_LIST:
            self.book_listbox.insert(tk.END, b)
        self.book_listbox.pack()
        self.book_listbox.bind("<<ListboxSelect>>", self.on_book_selected)

    def _build_buttons(self):
        btn_frm = ttk.Frame(self.root, padding=8)
        btn_frm.pack(fill="x", padx=12)

        ttk.Button(btn_frm, text="Add / Save Record", style="Blue.TButton", command=self.add_record).grid(row=0, column=0, padx=6)
        ttk.Button(btn_frm, text="Delete Selected", style="Blue.TButton", command=self.delete_selected).grid(row=0, column=1, padx=6)
        ttk.Button(btn_frm, text="Reset Fields", style="Blue.TButton", command=self.reset_fields).grid(row=0, column=2, padx=6)
        ttk.Button(btn_frm, text="Refresh / Load", style="Blue.TButton", command=self._load_records).grid(row=0, column=3, padx=6)
        ttk.Button(btn_frm, text="Export CSV", style="Blue.TButton", command=self.export_csv).grid(row=0, column=4, padx=6)
        ttk.Button(btn_frm, text="Exit", style="Blue.TButton", command=self._on_exit).grid(row=0, column=5, padx=6)

        ttk.Label(btn_frm, text="Search:").grid(row=1, column=0, pady=8, sticky="e")
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(btn_frm, textvariable=self.search_var, width=40)
        search_entry.grid(row=1, column=1, columnspan=3, sticky="w")
        ttk.Button(btn_frm, text="Go", style="Blue.TButton", command=self.search_records).grid(row=1, column=4, sticky="w", padx=6)


    def _build_treeview(self):
        frame = ttk.Frame(self.root, padding=8)
        frame.pack(fill="both", expand=True, padx=12, pady=6)

        columns = ("id", "member", "ref", "name", "mobile", "book_title", "author", "borrowed", "due", "days")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "id": "ID",
            "member": "Member Type",
            "ref": "Ref No",
            "name": "Name",
            "mobile": "Mobile",
            "book_title": "Book Title",
            "author": "Author",
            "borrowed": "Date Borrowed",
            "due": "Date Due",
            "days": "Days"
        }
        for col in columns:
            self.tree.heading(col, text=headings[col])
            widths = {"id": 40, "member": 100, "ref": 90, "name": 140, "mobile": 100,
                      "book_title": 160, "author": 120, "borrowed": 100, "due": 100, "days": 60}
            self.tree.column(col, width=widths[col], anchor="w")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self._on_tree_double_click)

    # ---------- Utility actions ----------
    def _ensure_dates(self):
        if not self.date_borrowed.get():
            today = datetime.date.today()
            self.date_borrowed.set(today.strftime(DATE_FORMAT))
        if not self.date_due.get():
            try:
                days = int(self.days_on_loan.get())
            except Exception:
                days = 14
            due = datetime.date.today() + datetime.timedelta(days=days)
            self.date_due.set(due.strftime(DATE_FORMAT))

    def on_book_selected(self, event):
        sel = self.book_listbox.curselection()
        if not sel:
            return
        book = self.book_listbox.get(sel[0])
        self.book_title.set(book)
        info = BOOK_MAPPING.get(book)
        if info:
            self.book_id.set(info.get("book_id", ""))
            self.author.set(info.get("author", ""))
            self.late_return_fine.set(info.get("late_return_fine", ""))
            self.selling_price.set(info.get("selling_price", ""))
            self.days_on_loan.set(info.get("days", 14))
        self._ensure_dates()

    def add_record(self):
        self._ensure_dates()
        if not self.book_title.get().strip() or not self.firstname.get().strip():
            messagebox.showwarning("Validation", "Please enter at least a firstname and book title.")
            return

        rec = {
            "member_type": self.member_type.get().strip(),
            "reference_no": self.reference.get().strip(),
            "title": self.title.get().strip(),
            "firstname": self.firstname.get().strip(),
            "surname": self.surname.get().strip(),
            "mobile": self.mobile.get().strip(),
            "address1": self.address1.get().strip(),
            "address2": self.address2.get().strip(),
            "postcode": self.postcode.get().strip(),
            "book_id": self.book_id.get().strip(),
            "book_title": self.book_title.get().strip(),
            "author": self.author.get().strip(),
            "date_borrowed": self.date_borrowed.get().strip(),
            "date_due": self.date_due.get().strip(),
            "days_on_loan": int(self.days_on_loan.get()),
            "late_return_fine": self.late_return_fine.get().strip(),
            "selling_price": self.selling_price.get().strip(),
            "date_overdue": self.date_overdue.get().strip(),
            "created_at": datetime.datetime.now().isoformat()
        }
        new_id = self.db.insert_record(rec)
        messagebox.showinfo("Saved", f"Record saved (ID {new_id}).")
        self.reset_fields()
        self._load_records()

    def reset_fields(self):
        for var in [self.member_type, self.reference, self.title, self.firstname, self.surname,
                    self.address1, self.address2, self.postcode, self.mobile, self.book_id,
                    self.book_title, self.author, self.late_return_fine, self.selling_price,
                    self.date_borrowed, self.date_due, self.date_overdue]:
            var.set("")
        self.days_on_loan.set(14)

    def _load_records(self, where_clause=None, params=()):
        for r in self.tree.get_children():
            self.tree.delete(r)
        rows = self.db.fetch_all(where_clause, params)
        for row in rows:
            rec_id = row[0]
            member = row[1]
            ref = row[2]
            name = f"{row[4]} {row[5]}"
            mobile = row[6]
            book_title = row[11]
            author = row[12]
            borrowed = row[13]
            due = row[14]
            days = row[15]
            self.tree.insert("", "end", iid=str(rec_id), values=(rec_id, member, ref, name, mobile, book_title, author, borrowed, due, days))

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Delete", "Select a record to delete.")
            return
        rec_id = int(sel[0])
        if messagebox.askyesno("Confirm Delete", f"Delete record ID {rec_id}?"):
            self.db.delete_by_id(rec_id)
            self._load_records()

    def search_records(self):
        q = self.search_var.get().strip()
        if not q:
            self._load_records()
            return
        clause = "firstname LIKE ? OR surname LIKE ? OR book_title LIKE ? OR reference_no LIKE ?"
        like_q = f"%{q}%"
        self._load_records(where_clause=clause, params=(like_q, like_q, like_q, like_q))

    def export_csv(self):
        rows = self.db.fetch_all()
        if not rows:
            messagebox.showinfo("Export", "No records to export.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return
        headers = ["id", "member_type", "reference_no", "title", "firstname", "surname", "mobile",
                   "address1", "address2", "postcode", "book_id", "book_title", "author",
                   "date_borrowed", "date_due", "days_on_loan", "late_return_fine",
                   "selling_price", "date_overdue", "created_at"]
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        messagebox.showinfo("Exported", f"Records exported to {os.path.abspath(file_path)}")

    def _on_tree_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        rec_id = int(item)
        rows = self.db.fetch_all("id = ?", (rec_id,))
        if rows:
            r = rows[0]
            self.member_type.set(r[1])
            self.reference.set(r[2])
            self.title.set(r[3])
            self.firstname.set(r[4])
            self.surname.set(r[5])
            self.mobile.set(r[6])
            self.address1.set(r[7])
            self.address2.set(r[8])
            self.postcode.set(r[9])
            self.book_id.set(r[10])
            self.book_title.set(r[11])
            self.author.set(r[12])
            self.date_borrowed.set(r[13])
            self.date_due.set(r[14])
            self.days_on_loan.set(r[15] if r[15] else 14)
            self.late_return_fine.set(r[16])
            self.selling_price.set(r[17])
            self.date_overdue.set(r[18])

    def _on_exit(self):
        if messagebox.askyesno("Exit", "Are you sure you want to quit?"):
            self.db.close()
            self.root.destroy()


# =========================
# MAIN PROGRAM
# =========================
def main():
    root = tk.Tk()
    root.title("Library System Login")
    root.geometry("400x200")

    def show_library_dashboard():
        root.geometry("1150x700")
        LibraryApp(root)

    login_frame = LoginFrame(root, show_library_dashboard)
    login_frame.pack(expand=True, fill="both")

    root.mainloop()

if __name__ == "__main__":
    main()
