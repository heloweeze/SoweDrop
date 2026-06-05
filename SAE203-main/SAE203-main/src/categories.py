AUTHORIZED_CATEGORIES = (
    "Admin",
    "Compte rendu",
    "Documentation",
    "Finance",
    "Inventaire",
    "Planning",
    "Procedure",
    "Projet",
    "RH",
    "Rapport",
    "Securite",
    "Technique",
)

CATEGORY_BY_LOWER_NAME = {
    category.lower(): category
    for category in AUTHORIZED_CATEGORIES
}
