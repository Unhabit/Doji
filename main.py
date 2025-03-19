from flask import Flask, render_template, request, redirect, flash, abort
import flask_login
import pymysql
from dynaconf import Dynaconf
from datetime import datetime


app = Flask(__name__)

conf = Dynaconf(
    settings_file = ["settings.toml"]
)

app = Flask(__name__)
app.secret_key = conf.secret_key

login_manager = flask_login.LoginManager()
login_manager.init_app(app)
login_manager.login_view = ('/signin')

class User:
    is_authenticated = True
    is_anonymous = False
    is_active = True

    def __init__(self, user_id, username, email, first_name, last_name):
        self.id = user_id
        self.username = username
        self.email = email
        self.first_name = first_name
        self.last_name = last_name


    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute(f"SELECT * FROM `Customer` WHERE `id` = {user_id};")

    result = cursor.fetchone()

    cursor.close
    conn.close

    if result is not None:
        return User(result["id"], result["username"], result["email"], result["first_name"], result["last_name"])
    


def connect_db():
    conn = pymysql.connect(
        host = "db.steamcenter.tech",
        database = "nshovo_doji",
        user = "nshovo",
        password = conf.password,
        autocommit = True,
        cursorclass= pymysql.cursors.DictCursor
    )

    return conn


@app.route("/")
def index():
    return render_template("homepage.html.jinja")


@app.route("/browse")
def product_browse():

    query = request.args.get('query')

    conn = connect_db()

    cursor = conn.cursor()

    if query is None:
        cursor.execute("SELECT * FROM  `Product` ;")
    else:
        cursor.execute(f"SELECT * FROM `Product` WHERE `name` LIKE '%{query}%' ;")

    results = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("browse.html.jinja", products = results, query=query)


@app.route("/product/<product_id>", methods=["POST", "GET"])
def product_page(product_id):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(f"SELECT * FROM `Product` WHERE `id` = {product_id};")
    product = cursor.fetchone()

    if product is None:
        abort(404)

    if request.method == "POST":
        customer_id = flask_login.current_user.id
        rating = request.form.get("rating")
        comment = request.form.get("comment")
        title = request.form.get("title", "No Title")

        if rating:
            cursor.execute(
                f"""
                INSERT INTO `Review` (`product_id`, `customer_id`, `rating`, `comment`, `timestamp`, `title`)
                VALUES ({product_id}, {customer_id}, {rating}, '{comment}', NOW(), '{title}')
                ON DUPLICATE KEY UPDATE 
                    `rating` = {rating}, 
                    `comment` = '{comment}', 
                    `timestamp` = NOW(),
                    `title` = '{title}';
                """
            )

    cursor.execute(
        f"""
        SELECT `Review`.`rating`, `Review`.`comment`, `Review`.`timestamp`, `Customer`.`username`
        FROM `Review`
        JOIN `Customer` ON `Review`.`customer_id` = `Customer`.`id`
        WHERE `Review`.`product_id` = {product_id};
        """
    )
    reviews = cursor.fetchall()

    cursor.execute(
        f"""
        SELECT ROUND(AVG(`rating`), 1) AS avg_rating
        FROM `Review`
        WHERE `product_id` = {product_id};
        """
    )
    avg_rating = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("product_page.html.jinja", product=product, avg_rating=avg_rating, reviews=reviews)

@app.route("/product/<product_id>/cart", methods=["POST"])
@flask_login.login_required
def add_to_cart(product_id):

    quantity = request.form["quantity"]
    customer_id = flask_login.current_user.id

    conn = connect_db()
    cursor = conn.cursor()

    
    cursor.execute(f"""
        INSERT INTO `Cart` (`customer_id`, `quantity`, `product_id`)
        VALUES ({customer_id}, {quantity}, {product_id})
        ON DUPLICATE KEY UPDATE 
            `quantity` = `quantity` + {quantity}
    """)

    cursor.close()
    conn.close()

    flash("Item successfully added to cart")
    return redirect("/cart")




@app.route("/signup", methods=["POST", "GET"])
def sign_up():
    if flask_login.current_user.is_authenticated:
        return redirect("/")
    
    if request.method == 'POST':
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        conn = connect_db()
    
        cursor = conn.cursor()
        
        if confirm_password != password:
            flash("Passwords does not match")
        
        if len(password)< 12 :
            flash("Your password must be at least 12 characters ")
            return render_template("signup.html.jinja")

        try:
            cursor.execute(f"""
                INSERT INTO `Customer` 
                    (`first_name`, `last_name`, `username`, `email`, `password`)
                VALUES
                    ( '{first_name}', '{last_name}', '{username}', '{email}', '{password}' );
            """)

        except pymysql.err.IntegrityError:
            flash("sorry, that username/email is already in use")
        
        else: 
            return redirect("/signin")
        
        finally:
            cursor.close
            conn.close

        return redirect("/signin")



    return render_template("signup.html.jinja")


@app.route("/signin", methods=["POST", "GET"])
def sign_in():
    if flask_login.current_user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        username = request.form['username'].strip()
        password = request.form['password']

        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute(f"SELECT * FROM `Customer` WHERE `username` = '{username}';")

        result = cursor.fetchone()

        if result is None: 
            flash("username or password is incorrect")
        elif password != result["password"]:
            flash("username or password is incorrect")
        else:
            user = User(result["id"], result["username"], result["email"], result["first_name"], result["last_name"])

            flask_login.login_user(user)
            
            return redirect('/')


    return render_template("signin.html.jinja")

@app.route('/logout')
def logout():
    flask_login.logout_user()
    return  redirect('/')


@app.route("/cart")
@flask_login.login_required
def cart():
    customer_id = flask_login.current_user.id
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(f"SELECT `name`, `price`, `Cart`.`quantity`, `product_image`, `product_id`, `Cart`.`id` FROM `Cart` JOIN `Product` ON `product_id` = `Product`.`id` WHERE `customer_id`= 1;")

    results = cursor.fetchall()

    total=0
    for item in results:
        total+=item['price'] * item['quantity']

    cursor.close()
    conn.close()


    return render_template("cart.html.jinja" , products = results, total=total)

@app.route("/cart/remove", methods=["POST"])
@flask_login.login_required
def remove_item():
    cart_id = request.form.get("cart_id")
    customer_id = flask_login.current_user.id

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(f"DELETE FROM `Cart` WHERE `id` = {cart_id} AND `customer_id` = {customer_id};")
    
    cursor.close()
    conn.close()

    flash("Item removed from cart successfully.")
    return redirect("/cart")

@app.route("/cart/update", methods=["POST"])
@flask_login.login_required
def update_quantity():
    cart_id = request.form.get("cart_id")
    new_quantity = int(request.form.get("quantity"))
    customer_id = flask_login.current_user.id   

    if new_quantity < 1:
        flash("Quantity must be at least 1.")
        return redirect("/cart")

    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute(f"""
        UPDATE `Cart`
        SET `quantity` = {new_quantity}
        WHERE `id` = {cart_id} AND `customer_id` = {customer_id};
    """)

    cursor.close()
    conn.close()

    flash("Cart updated successfully.")
    return redirect("/cart")


@app.route("/cart/checkout", methods=["GET", "POST"])
@flask_login.login_required
def checkout():
    customer_id = flask_login.current_user.id
    conn = connect_db()
    cursor = conn.cursor()

    NY_SALES_TAX_RATE = 0.08875  
    SHIPPING_COST = 5.99

    cursor.execute(f"""
            SELECT `Product`.`price`, `Cart`.`quantity`
            FROM `Cart`
            JOIN `Product` ON `Cart`.`product_id` = `Product`.`id`
            WHERE `Cart`.`customer_id` = {customer_id};
        """)
    cart_items = cursor.fetchall()

    subtotal = sum(item['price'] * item['quantity'] for item in cart_items)
    tax = subtotal * NY_SALES_TAX_RATE
    total = subtotal + tax + SHIPPING_COST

    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email").strip()
        phone = request.form.get("phone").strip()
        street = request.form.get("street").strip()
        city = request.form.get("city").strip()
        state = request.form.get("state").strip()
        zip_code = request.form.get("zip").strip()

        cursor.execute(f"""
            INSERT INTO Sale 
                (customer_id, status, timestamp, first_name, last_name, email, phone, street, city, state, zip_code)
            VALUES 
                ({customer_id}, 2 , NOW() , '{first_name}', '{last_name}', '{email}', '{phone}', '{street}', '{city}', '{state}', '{zip_code}');
        """)

        cursor.execute(f"DELETE FROM `Cart` WHERE `customer_id` = {customer_id};")
        cursor.close()
        conn.close()

        flash("Order placed successfully!")
        return redirect("/")

    cursor.execute(f"""
        SELECT `Product`.`name`, `Product`.`price`, `Cart`.`quantity`, `Product`.`product_image`
        FROM `Cart`
        JOIN `Product` ON `Cart`.`product_id` = `Product`.`id`
        WHERE `Cart`.`customer_id` = {customer_id};
    """)

    cart_items = cursor.fetchall()

    if subtotal >= 24.98:
        SHIPPING_COST = 0.00

    total = sum(item['price'] * item['quantity'] for item in cart_items)
    tax = subtotal * NY_SALES_TAX_RATE
    total = subtotal + tax + SHIPPING_COST

    cursor.close()
    conn.close()

    return render_template("checkout.html.jinja", cart_items=cart_items, total=total, subtotal=subtotal, tax=tax, shipping=SHIPPING_COST)

@app.route("/cart/checkout/thankyou")
def thankyou():
    return ("ORDER PLACED")

@app.route("/contact")
def contact():

    return render_template ("contact.html.jinja")