from flask import Flask, render_template, request, redirect, flash, abort
import flask_login
import pymysql
from dynaconf import Dynaconf


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
        host = "10.100.34.80",
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


@app.route("/product/<product_id>")
def product_page(product_id):

    conn = connect_db()

    cursor = conn.cursor()
    
    cursor.execute(f"SELECT * FROM `Product` WHERE `id` = {product_id} ;")

    results = cursor.fetchone()

    cursor.close()
    conn.close()
    
    if results is None:
        abort(404)

    return render_template( "product_page.html.jinja",  product=results)

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
