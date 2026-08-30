const ingredientInput =
    document.querySelector("#ingredientInput");

const addIngredientBtn =
    document.querySelector("#addIngredientBtn");

const findButton =
    document.querySelector("#findButton");

const chipsContainer =
    document.querySelector("#chips");

const suggestedButtons =
    document.querySelectorAll(".suggested-chip");


// =========================================
// INGREDIENT LIST
// =========================================

let selectedIngredients = [];


// =========================================
// ADD INGREDIENT
// =========================================

function addIngredient(ingredient) {

    ingredient =
        ingredient.trim().toLowerCase();

    if (ingredient === "") {
        return;
    }

    // Don't add duplicate ingredients
    if (
        selectedIngredients.includes(
            ingredient
        )
    ) {
        return;
    }

    selectedIngredients.push(
        ingredient
    );

    updateIngredients();
}


// =========================================
// UPDATE INGREDIENT CHIPS
// =========================================

function updateIngredients() {

    chipsContainer.innerHTML = "";

    // No ingredients selected
    if (
        selectedIngredients.length === 0
    ) {

        chipsContainer.innerHTML = `
            <span class="empty-message">
                No ingredients selected yet
            </span>
        `;

        return;
    }


    // Create chips
    selectedIngredients.forEach(
        function(ingredient) {

            const chip =
                document.createElement("span");

            chip.className =
                "chip selected-chip";

            chip.dataset.ingredient =
                ingredient;

            chip.innerHTML = `
                ${ingredient}
                <button
                    type="button"
                    class="remove-chip"
                >
                    ×
                </button>
            `;


            // Remove ingredient
            chip
                .querySelector(".remove-chip")
                .addEventListener(
                    "click",
                    function() {

                        selectedIngredients =
                            selectedIngredients.filter(
                                function(item) {

                                    return item !==
                                        ingredient;

                                }
                            );

                        updateIngredients();

                    }
                );


            chipsContainer.appendChild(
                chip
            );

        }
    );

}


// =========================================
// QUICK ADD BUTTONS
// =========================================

suggestedButtons.forEach(
    function(button) {

        button.addEventListener(
            "click",
            function() {

                const ingredient =
                    button.dataset.ingredient;

                addIngredient(
                    ingredient
                );

            }
        );

    }
);


// =========================================
// ADD BUTTON
// =========================================

addIngredientBtn.addEventListener(
    "click",
    function() {

        addIngredientsFromInput();

    }
);


// =========================================
// ENTER KEY
// =========================================

ingredientInput.addEventListener(
    "keydown",
    function(event) {

        if (event.key === "Enter") {

            event.preventDefault();

            addIngredientsFromInput();

        }

    }
);


// =========================================
// ADD FROM INPUT
// =========================================

function addIngredientsFromInput() {

    const value =
        ingredientInput.value.trim();

    if (value === "") {
        return;
    }


    // Allow multiple ingredients
    // Example:
    // eggs, flour, milk

    const ingredients =
        value.split(",");


    ingredients.forEach(
        function(ingredient) {

            addIngredient(
                ingredient
            );

        }
    );


    // Clear input
    ingredientInput.value = "";

}


// =========================================
// FIND MY RECIPES
// =========================================

findButton.addEventListener(
    "click",
    function() {

        // If user typed something but
        // didn't press Add, add it first
        addIngredientsFromInput();


        // Check selected ingredients
        if (
            selectedIngredients.length === 0
        ) {

            alert(
                "Please add at least one ingredient."
            );

            return;
        }


        // Convert ingredients to URL text
        const ingredientsText =
            selectedIngredients.join(",");


        // Open SEPARATE RESULTS PAGE
        window.location.href =
            "/results?ingredients=" +
            encodeURIComponent(
                ingredientsText
            );

    }
);