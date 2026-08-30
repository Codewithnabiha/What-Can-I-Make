import sqlite3
import json
import secrets
import os
import base64


from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, session, redirect, url_for
from authlib.integrations.flask_client import OAuth
from flask_mail import Mail, Message  # type: ignore[reportMissingImports]

try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency for local env loading
    def load_dotenv(*args, **kwargs):
        return False

# =========================================
# GOOGLE CREDENTIALS
# =========================================


import os

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# =========================================
# APP
# =========================================

app = Flask(__name__)

app.secret_key = "what-can-i-make-secret-key"

#========================================
# MAIL CONFIGURATION
#========================================
load_dotenv()

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")

mail = Mail(app)
# =========================================
# DATABASE
# =========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "users.db")


def get_db():
    return sqlite3.connect(DATABASE)


def init_db():

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email_verified INTEGER DEFAULT 0,
            verification_token TEXT
        )
    """)

    # Favorites table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            recipe_name TEXT NOT NULL,
            UNIQUE(user_id, recipe_name),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    # Personal Recipes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personal_recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            ingredients TEXT NOT NULL,
            time TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            instructions TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
         """)
            # Cooking History table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cooking_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            recipe_name TEXT NOT NULL,
            viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
   """)
    conn.commit()
    conn.close()


init_db()
     

def send_verification_email(email, token):

    verification_link = url_for(
        "verify_email",
        token=token,
        _external=True
    )

    message = Message(
        subject="Verify your What Can I Make? account",
        sender=app.config["MAIL_USERNAME"],
        recipients=[email]
    )

    message.body = f"""
Hello!

Thanks for signing up for What Can I Make?

Please verify your email by clicking this link:

{verification_link}

If you did not create this account, you can ignore this email.
"""

    mail.send(message)

# =========================================
# GOOGLE LOGIN
# =========================================

oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid profile email"
    }
)


# =========================================
# NORMALIZE INGREDIENT
# =========================================

def normalize_ingredient(ingredient):

    ingredient = ingredient.strip().lower()

    if ingredient.endswith("ies"):
        ingredient = ingredient[:-3] + "y"

    elif ingredient.endswith("oes"):
        ingredient = ingredient[:-2]

    elif ingredient.endswith("es"):
        ingredient = ingredient[:-2]

    elif ingredient.endswith("s"):
        ingredient = ingredient[:-1]

    return ingredient
def add_diet_tags(recipe):

    recipe = recipe.copy()

    diets = recipe.get("diet", [])

    if isinstance(diets, str):
        diets = [diets]

    diets = set(diets)

    ingredients = recipe.get("ingredients", [])

    text = " ".join(
        [recipe.get("name", "")] + ingredients
    ).lower()

    # Vegetarian
    meat = [
        "chicken",
        "beef",
        "mutton",
        "lamb",
        "fish",
        "prawn",
        "shrimp",
        "bacon",
        "sausage",
        "meat"
    ]

    if not any(item in text for item in meat):
        diets.add("vegetarian")

    # Vegan
    animal_products = meat + [
        "egg",
        "eggs",
        "milk",
        "cheese",
        "yogurt",
        "butter",
        "cream",
        "ghee"
    ]

    if not any(item in text for item in animal_products):
        diets.add("vegan")

    # Healthy
    healthy_words = [
        "vegetable",
        "spinach",
        "broccoli",
        "carrot",
        "tomato",
        "cucumber",
        "peas",
        "beans",
        "lentils",
        "chickpea",
        "oats",
        "fruit",
        "apple",
        "banana",
        "avocado",
        "salad"
    ]

    if any(item in text for item in healthy_words):
        diets.add("healthy")

    recipe["diet"] = list(diets)

    return recipe
# =========================================
# LOAD RECIPES
# =========================================

def load_recipes():

    with open(
        "recipes.json",
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# =========================================
# HOME
# =========================================

# =========================================
# HOME
# =========================================

@app.route("/")
def home():

    recipes = load_recipes()

    # First 3 recipes for Popular Right Now
    popular_recipes = recipes[:3]

    return render_template(
        "index.html",
        popular_recipes=popular_recipes
    )

                 
# =========================================
# RESULTS
# =========================================


@app.route("/results")
def results_page():

    ingredients_text = request.args.get(
        "ingredients",
        ""
    )

    ingredients = [
        normalize_ingredient(item)
        for item in ingredients_text.split(",")
        if item.strip()
    ]

    recipes = load_recipes()

    possible_recipes = []

    for recipe in recipes:

        recipe_ingredients = [
            normalize_ingredient(item)
            for item in recipe["ingredients"]
        ]

        matched = [
            ingredient
            for ingredient in recipe_ingredients
            if ingredient in ingredients
        ]

        missing = [
            ingredient
            for ingredient in recipe_ingredients
            if ingredient not in ingredients
        ]

        # Calculate match percentage
        if len(recipe_ingredients) > 0:

            match_percentage = round(
                len(matched)
                / len(recipe_ingredients)
                * 100
            )

        else:
            match_percentage = 0

        # Show recipes with at least 60% matching ingredients
        if match_percentage >= 60:

            recipe_copy = recipe.copy()

            recipe_copy["matched"] = matched
            recipe_copy["missing"] = missing
            recipe_copy["match_percentage"] = match_percentage

            possible_recipes.append(
                recipe_copy
            )

    # Highest match first
    possible_recipes.sort(
        key=lambda recipe: recipe["match_percentage"],
        reverse=True
    )

    # Show top 6 matching recipes
    possible_recipes = possible_recipes[:6]

    return render_template(
        "results.html",
        ingredients=ingredients,
        recipes=possible_recipes
    )
# =========================================
# RECIPE CATEGORIES
# =========================================

def get_recipe_categories(recipe):

    name = recipe["name"].lower()

    ingredients = [
        item.lower()
        for item in recipe.get("ingredients", [])
    ]

    categories = []

    # =========================================
    # VEGETARIAN / NON-VEGETARIAN
    # =========================================

    non_veg_words = [
        "chicken",
        "beef",
        "mutton",
        "lamb",
        "fish",
        "tuna",
        "prawn",
        "prawns",
        "shrimp",
        "meat",
        "keema",
        "mince"
    ]

    is_non_veg = (
        any(word in name for word in non_veg_words)
        or any(
            word in ingredient
            for ingredient in ingredients
            for word in non_veg_words
        )
    )

    if not is_non_veg:
        categories.append("vegetarian")

    # =========================================
    # BREAKFAST
    # =========================================

    breakfast_words = [
        "pancake",
        "toast",
        "omelette",
        "omelet",
        "egg",
        "paratha",
        "oatmeal",
        "sandwich"
    ]

    if any(word in name for word in breakfast_words):
        categories.append("breakfast")

    # =========================================
    # QUICK & EASY
    # =========================================

    time_text = recipe.get("time", "0 min")

    try:
        minutes = int(
            time_text.replace("min", "").strip()
        )

        if minutes <= 30:
            categories.append("quick")

    except (ValueError, AttributeError):
        pass

    # =========================================
    # PAKISTANI FAVORITES
    # =========================================

    pakistani_words = [
        "biryani",
        "karahi",
        "paratha",
        "daal",
        "dal",
        "aloo",
        "gobi",
        "chana",
        "rajma",
        "bhindi",
        "pulao",
        "lobia",
        "samosa",
        "chaat",
        "curry",
        "tikka"
    ]

    if any(word in name for word in pakistani_words):
        categories.append("pakistani")

    # =========================================
    # BUDGET FRIENDLY
    # =========================================

    budget_ingredients = [
        "potato",
        "bread",
        "egg",
        "eggs",
        "rice",
        "flour",
        "lentils",
        "onion",
        "tomato"
    ]

    cheap_count = sum(
        1
        for ingredient in ingredients
        if any(
            cheap_item in ingredient
            for cheap_item in budget_ingredients
        )
    )

    if cheap_count >= 2:
        categories.append("budget")

    return categories

# =========================================
# CATEGORY PAGE
# =========================================

@app.route("/category/<category>")
def category_page(category):

    recipes = load_recipes()

    category_recipes = []

    for recipe in recipes:

        categories = get_recipe_categories(recipe)

        if category == "all":
            category_recipes.append(recipe)

        elif category in categories:
            category_recipes.append(recipe)

    return render_template(
        "category.html",
        recipes=category_recipes,
        category=category
    )
# =========================================
# SMART MEAL PLANNER
# =========================================

import random


@app.route("/meal-planner")
def meal_planner():

    recipes = load_recipes()

    if not recipes:
        return render_template(
            "meal_planner.html",
            meal_plan={}
        )

    # Separate recipes by meal type
    breakfast_recipes = []
    lunch_recipes = []
    dinner_recipes = []

    for recipe in recipes:

        categories = get_recipe_categories(recipe)

        name = recipe["name"].lower()

        # Breakfast recipes
        breakfast_words = [
            "pancake",
            "toast",
            "omelette",
            "omelet",
            "egg",
            "paratha",
            "oatmeal"
        ]

        if (
            "breakfast" in categories
            or any(word in name for word in breakfast_words)
        ):
            breakfast_recipes.append(recipe)

        # Dinner recipes
        dinner_words = [
            "biryani",
            "karahi",
            "curry",
            "pulao",
            "rice",
            "daal",
            "dal",
            "chicken",
            "tikka"
        ]

        if any(word in name for word in dinner_words):
            dinner_recipes.append(recipe)

    # Lunch can use all recipes
    lunch_recipes = recipes.copy()

    # Fallbacks if a category has no recipes
    if not breakfast_recipes:
        breakfast_recipes = recipes.copy()

    if not dinner_recipes:
        dinner_recipes = recipes.copy()

    days = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday"
    ]

    meal_plan = {}

    for day in days:

        meal_plan[day] = {
            "breakfast": random.choice(breakfast_recipes),
            "lunch": random.choice(lunch_recipes),
            "dinner": random.choice(dinner_recipes)
        }

    return render_template(
        "meal_planner.html",
        meal_plan=meal_plan
    )
# =========================================
# COOKING HISTORY
# =========================================

@app.route("/history")
def cooking_history():

    # User must be logged in
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT recipe_name, viewed_at
        FROM cooking_history
        WHERE user_id = ?
        ORDER BY viewed_at DESC
        """,
        (user_id,)
    )

    history = cursor.fetchall()

    conn.close()

    recipes = load_recipes()

    history_recipes = []

    for recipe_name, viewed_at in history:

        for recipe in recipes:

            if recipe["name"] == recipe_name:

                recipe_copy = recipe.copy()
                recipe_copy["viewed_at"] = viewed_at

                history_recipes.append(recipe_copy)

                break

    return render_template(
        "history.html",
        recipes=history_recipes
    )
# =========================================
# RECIPE DETAIL
# =========================================
@app.route("/recipe/<recipe_name>")
def recipe_detail(recipe_name):

    recipes = load_recipes()

    selected_recipe = None

    for recipe in recipes:

        if recipe["name"].lower() == recipe_name.lower():

            selected_recipe = recipe
            break

    if selected_recipe is None:
        return "Recipe not found", 404
        # Save recipe to cooking history
    if session.get("logged_in"):

        user_id = session.get("user_id")

        conn = get_db()
        cursor = conn.cursor()

        # Remove previous entry of the same recipe
        cursor.execute(
            """
            DELETE FROM cooking_history
            WHERE user_id = ?
            AND recipe_name = ?
            """,
            (user_id, selected_recipe["name"])
        )

        # Add recipe as latest viewed recipe
        cursor.execute(
            """
            INSERT INTO cooking_history (
                user_id,
                recipe_name
            )
            VALUES (?, ?)
            """,
            (
                user_id,
                selected_recipe["name"]
            )
        )

        conn.commit()
        conn.close()


    # Check if recipe is already a favorite
    is_favorite = False

    if session.get("logged_in"):

        user_id = session.get("user_id")

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id
            FROM favorites
            WHERE user_id = ?
            AND recipe_name = ?
            """,
            (user_id, selected_recipe["name"])
        )

        favorite = cursor.fetchone()

        conn.close()

        if favorite:
            is_favorite = True


    return render_template(
        "recipe.html",
        recipe=selected_recipe,
        is_favorite=is_favorite
    )
# =========================================
# SURPRISE ME - RANDOM RECIPE
# =========================================

@app.route("/surprise-me")
def surprise_me():

    recipes = load_recipes()

    if not recipes:
        return "No recipes available", 404

    random_recipe = random.choice(recipes)

    return redirect(
        url_for(
            "recipe_detail",
            recipe_name=random_recipe["name"]
        )
    )
# =========================================
# COOKING STATS
# =========================================

@app.route("/cooking-stats")
def cooking_stats():

    # User must be logged in
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    conn = get_db()
    cursor = conn.cursor()

    # Total favorite recipes
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM favorites
        WHERE user_id = ?
        """,
        (user_id,)
    )

    total_favorites = cursor.fetchone()[0]

    # Total personal recipes
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM personal_recipes
        WHERE user_id = ?
        """,
        (user_id,)
    )

    total_personal_recipes = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "cooking_stats.html",
        total_favorites=total_favorites,
        total_personal_recipes=total_personal_recipes
    )
# =========================================
# DIET FILTERS
# =========================================

@app.route("/diet-filters")
def diet_filters():

    recipes = load_recipes()

    return render_template(
        "diet_filters.html",
        recipes=recipes
    )
# =========================================
# DIET RECIPE RESULTS
# =========================================
@app.route("/diet/<diet>")
def diet_recipes(diet):

    recipes = load_recipes()

    filtered_recipes = []

    for recipe in recipes:

        recipe = add_diet_tags(recipe)

        recipe_diets = recipe.get("diet", [])

        if isinstance(recipe_diets, str):
            recipe_diets = [recipe_diets]

        recipe_diets = [
            str(d).lower().strip()
            for d in recipe_diets
        ]

        if diet.lower() in recipe_diets:
            filtered_recipes.append(recipe)

    return render_template(
        "category.html",
        recipes=filtered_recipes,
        category=diet.lower()
    )
# =========================================
# LOGIN
# =========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not email or not password:

            return render_template(
                "login.html",
                error="Please fill in all fields."
            )

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, name, email, password, email_verified
            FROM users
            WHERE email = ?
            """,
            (email,)
        )

        user = cursor.fetchone()

        conn.close()

        if user is None:

            return render_template(
                "login.html",
                error="No account found with this email."
            )
        
        if user[4] == 0:

            return render_template(
                "login.html",
                error="Please verify your email before logging in."
            )
        
        if not check_password_hash(
            user[3],
            password
        ):

            return render_template(
                "login.html",
                error="Incorrect password."
            )

        session["logged_in"] = True
        session["user_id"] = user[0]
        session["username"] = user[1]
        session["email"] = user[2]

        return redirect(
            url_for("home")
        )

    return render_template("login.html")


# =========================================
# SIGN UP
# =========================================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not name or not email or not password or not confirm_password:

            return render_template(
                "signup.html",
                error="Please fill in all fields."
            )

        if password != confirm_password:

            return render_template(
                "signup.html",
                error="Passwords do not match."
            )

        if len(password) < 6:

            return render_template(
                "signup.html",
                error="Password must be at least 6 characters."
            )

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:

            conn.close()

            return render_template(
                "signup.html",
                error="An account with this email already exists."
            )

        hashed_password = generate_password_hash(
            password
        )
        verification_token = secrets.token_urlsafe(32)

        cursor.execute(
            """
            INSERT INTO users (
                name,
                email,
                password,
                email_verified,
                verification_token
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                email,
                hashed_password,
                0,
                verification_token
            )
        )

        conn.commit()
        send_verification_email(
            email,
            verification_token
        )
        conn.close()

        return render_template(
            "login.html",
            success="Account created! Please check your email and verify your account before logging in."
        )

    return render_template("signup.html")
#===========================
#email verification
#============================
@app.route("/verify/<token>")
def verify_email(token):

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id
        FROM users
        WHERE verification_token = ?
        """,
        (token,)
    )

    user = cursor.fetchone()

    if user is None:
        conn.close()

        return render_template(
            "login.html",
            error="This verification link is invalid or has already been used."
        )

    cursor.execute(
        """
        UPDATE users
        SET email_verified = 1,
            verification_token = NULL
        WHERE id = ?
        """,
        (user[0],)
    )

    conn.commit()
    conn.close()

    return render_template(
        "login.html",
        success="Email verified successfully! You can now log in."
    )
    

#==========================================
#resend verification email
#=========================================
@app.route("/resend-verification", methods=["GET", "POST"])
def resend_verification():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, email_verified
            FROM users
            WHERE email = ?
            """,
            (email,)
        )

        user = cursor.fetchone()

        if user is None:
            conn.close()

            return render_template(
                "login.html",
                error="No account found with this email."
            )

        if user[1] == 1:
            conn.close()

            return render_template(
                "login.html",
                error="This email is already verified. You can log in."
            )

        new_token = secrets.token_urlsafe(32)

        cursor.execute(
            """
            UPDATE users
            SET verification_token = ?
            WHERE id = ?
            """,
            (new_token, user[0])
        )

        conn.commit()
        conn.close()

        send_verification_email(email, new_token)

        return render_template(
            "login.html",
            success="A new verification email has been sent. Please check your inbox."
        )

    return render_template("resend_verification.html")
# =========================================
# FAVORITES
# =========================================

@app.route("/favorite/<recipe_name>", methods=["POST"])
def add_favorite(recipe_name):

    # User must be logged in
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO favorites (user_id, recipe_name)
            VALUES (?, ?)
            """,
            (user_id, recipe_name)
        )

        conn.commit()

    except sqlite3.IntegrityError:
        # Recipe already saved
        pass

    conn.close()

    return redirect(
        url_for(
            "recipe_detail",
            recipe_name=recipe_name
        )
    )


@app.route("/unfavorite/<recipe_name>", methods=["POST"])
def remove_favorite(recipe_name):

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM favorites
        WHERE user_id = ?
        AND recipe_name = ?
        """,
        (user_id, recipe_name)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for(
            "recipe_detail",
            recipe_name=recipe_name
        )
    )


@app.route("/favorites")
def favorites():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT recipe_name
        FROM favorites
        WHERE user_id = ?
        """,
        (user_id,)
    )

    favorite_names = [
        row[0]
        for row in cursor.fetchall()
    ]

    conn.close()

    recipes = load_recipes()

    favorite_recipes = [
        recipe
        for recipe in recipes
        if recipe["name"] in favorite_names
    ]

    return render_template(
        "favorites.html",
        recipes=favorite_recipes
    )
   # =========================================
# PERSONAL RECIPES
# =========================================

@app.route("/create-recipe", methods=["GET", "POST"])
def create_recipe():

    # User must be logged in
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        ingredients = request.form.get("ingredients", "").strip()
        time = request.form.get("time", "").strip()
        difficulty = request.form.get("difficulty", "").strip()
        instructions = request.form.get("instructions", "").strip()

        # Check fields
        if not name or not ingredients or not time or not difficulty or not instructions:

            return render_template(
                "create_recipe.html",
                error="Please fill in all fields."
            )

        user_id = session.get("user_id")

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO personal_recipes (
                user_id,
                name,
                ingredients,
                time,
                difficulty,
                instructions
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                name,
                ingredients,
                time,
                difficulty,
                instructions
            )
        )

        conn.commit()
        conn.close()

        return redirect(
            url_for("my_recipes")
        )

    return render_template("create_recipe.html")


@app.route("/my-recipes")
def my_recipes():

    # User must be logged in
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, name, ingredients, time, difficulty, instructions
        FROM personal_recipes
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,)
    )

    recipes = cursor.fetchall()

    conn.close()

    return render_template(
        "my_recipes.html",
        recipes=recipes
    )

@app.route("/my-recipe/<int:recipe_id>")
def my_recipe_detail(recipe_id):

    # User must be logged in
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, name, ingredients, time, difficulty, instructions
        FROM personal_recipes
        WHERE id = ?
        AND user_id = ?
        """,
        (recipe_id, user_id)
    )

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return "Recipe not found", 404

    # Convert database data into the same format
    # used by recipe.html
    recipe = {
        "name": row[1],
        "ingredients": [
            item.strip()
            for item in row[2].split(",")
            if item.strip()
        ],
        "time": row[3],
        "difficulty": row[4],
        "steps": [
            step.strip()
            for step in row[5].split("\n")
            if step.strip()
        ]
    }

    return render_template(
        "recipe.html",
        recipe=recipe,
        is_favorite=False
    )
@app.route("/delete-my-recipe/<int:recipe_id>", methods=["POST"])
def delete_my_recipe(recipe_id):

    # User must be logged in
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    conn = get_db()
    cursor = conn.cursor()

    # Delete only if this recipe belongs to the logged-in user
    cursor.execute(
        """
        DELETE FROM personal_recipes
        WHERE id = ?
        AND user_id = ?
        """,
        (recipe_id, user_id)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("my_recipes")
    ) 
# =========================================
# LOGOUT
# =========================================

@app.route("/signout")
def signout():

    session.clear()

    return redirect(
        url_for("home")
    )


# =========================================
# GOOGLE LOGIN
# =========================================

@app.route("/google/login")
def google_login():

    redirect_uri = url_for(
        "google_callback",
        _external=True
    )

    return google.authorize_redirect(
        redirect_uri
    )


# =========================================
# GOOGLE CALLBACK
# =========================================

@app.route("/google/callback")
def google_callback():

    token = google.authorize_access_token()

    userinfo = token["userinfo"]

    session["logged_in"] = True

    session["username"] = userinfo.get(
        "name",
        "Google User"
    )

    session["email"] = userinfo.get(
        "email",
        ""
    )

    return redirect(
        url_for("home")
    )


# =========================================
# RUN
# =========================================

if __name__ == "__main__":

    app.run(debug=True)