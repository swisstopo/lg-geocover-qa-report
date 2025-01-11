import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
from tkinter import ttk


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("File Loader")
        self.geometry("800x600")

        self.btn_load_file = tk.Button(self, text="Load File", command=self.load_file)
        self.btn_load_file.pack(pady=20)

        self.table_frame = tk.Frame(self)
        self.table_frame.pack(fill=tk.BOTH, expand=True)

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
        if file_path:
            self.load_data(file_path)

    def load_data(self, file_path):
        try:
            data = pd.read_csv(file_path)
            self.display_table(data)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file:\n{e}")

    def display_table(self, data):
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        tree = ttk.Treeview(self.table_frame, columns=list(data.columns), show="headings")
        tree.pack(fill=tk.BOTH, expand=True)

        for col in data.columns:
            tree.heading(col, text=col)
            tree.column(col, anchor=tk.W)

        for index, row in data.iterrows():
            tree.insert("", tk.END, values=list(row))


if __name__ == "__main__":
    app = App()
    app.mainloop()
