from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from sqlalchemy import func, extract
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# ตรวจสอบว่าอยู่บน Vercel หรือไม่
if os.environ.get('VERCEL_ENV'):
    # ใช้ in-memory database บน Vercel
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
else:
    # ใช้ file database ใน local
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# โมเดลฐานข้อมูลสำหรับค่าใช้จ่าย
class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Expense {self.description}: {self.amount}>'

# สร้างตารางฐานข้อมูล
with app.app_context():
    db.create_all()
    
    # เพิ่มข้อมูลตัวอย่างสำหรับ Vercel
    if os.environ.get('VERCEL_ENV') and not Expense.query.first():
        sample_expenses = [
            Expense(
                date=date.today(),
                category='อาหาร',
                description='อาหารเช้า - ข้าวผัด',
                amount=45.0
            ),
            Expense(
                date=date.today(),
                category='เครื่องดื่ม',
                description='กาแฟ - คาปูชิโน่',
                amount=65.0
            ),
            Expense(
                date=date.today(),
                category='ค่าเดินทาง',
                description='ค่าแท็กซี่',
                amount=120.0
            )
        ]
        
        for expense in sample_expenses:
            db.session.add(expense)
        
        db.session.commit()

@app.route('/')
def index():
    # แสดงรายการค่าใช้จ่ายล่าสุด
    expenses = Expense.query.order_by(Expense.date.desc()).limit(10).all()
    
    # คำนวณยอดรวมของเดือนปัจจุบัน
    current_month = date.today().month
    current_year = date.today().year
    monthly_total = db.session.query(func.sum(Expense.amount)).filter(
        extract('month', Expense.date) == current_month,
        extract('year', Expense.date) == current_year
    ).scalar() or 0
    
    return render_template('index.html', expenses=expenses, monthly_total=monthly_total)

@app.route('/add', methods=['GET', 'POST'])
def add_expense():
    if request.method == 'POST':
        try:
            expense = Expense(
                date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
                category=request.form['category'],
                description=request.form['description'],
                amount=float(request.form['amount'])
            )
            db.session.add(expense)
            db.session.commit()
            flash('เพิ่มรายการค่าใช้จ่ายเรียบร้อยแล้ว!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash('เกิดข้อผิดพลาดในการเพิ่มข้อมูล', 'error')
            return redirect(url_for('add_expense'))
    
    return render_template('add_expense.html', date=date)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_expense(id):
    expense = Expense.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            expense.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            expense.category = request.form['category']
            expense.description = request.form['description']
            expense.amount = float(request.form['amount'])
            
            db.session.commit()
            flash('แก้ไขรายการค่าใช้จ่ายเรียบร้อยแล้ว!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash('เกิดข้อผิดพลาดในการแก้ไขข้อมูล', 'error')
    
    return render_template('edit_expense.html', expense=expense, date=date)

@app.route('/delete/<int:id>')
def delete_expense(id):
    expense = Expense.query.get_or_404(id)
    try:
        db.session.delete(expense)
        db.session.commit()
        flash('ลบรายการค่าใช้จ่ายเรียบร้อยแล้ว!', 'success')
    except Exception as e:
        flash('เกิดข้อผิดพลาดในการลบข้อมูล', 'error')
    
    return redirect(url_for('index'))

@app.route('/reports')
def reports():
    # รายงานรายเดือน
    monthly_data = db.session.query(
        extract('year', Expense.date).label('year'),
        extract('month', Expense.date).label('month'),
        func.sum(Expense.amount).label('total')
    ).group_by(
        extract('year', Expense.date),
        extract('month', Expense.date)
    ).order_by(
        extract('year', Expense.date).desc(),
        extract('month', Expense.date).desc()
    ).limit(12).all()
    
    # รายงานตามหมวดหมู่
    category_data = db.session.query(
        Expense.category,
        func.sum(Expense.amount).label('total')
    ).group_by(Expense.category).order_by(
        func.sum(Expense.amount).desc()
    ).all()
    
    return render_template('reports.html', monthly_data=monthly_data, category_data=category_data)

@app.route('/api/monthly-chart')
def monthly_chart_data():
    # ข้อมูลสำหรับกราฟรายเดือน
    monthly_data = db.session.query(
        extract('year', Expense.date).label('year'),
        extract('month', Expense.date).label('month'),
        func.sum(Expense.amount).label('total')
    ).group_by(
        extract('year', Expense.date),
        extract('month', Expense.date)
    ).order_by(
        extract('year', Expense.date),
        extract('month', Expense.date)
    ).limit(12).all()
    
    labels = []
    data = []
    
    for item in monthly_data:
        month_names = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
                      'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
        labels.append(f"{month_names[int(item.month)]} {int(item.year)}")
        data.append(float(item.total))
    
    return jsonify({
        'labels': labels,
        'data': data
    })

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)