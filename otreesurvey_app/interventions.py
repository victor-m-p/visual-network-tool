"""
Intervention texts shown to participants.

Each intervention has:
  label : short identifier logged in the data
  title : brief descriptive title (not shown to participants)
  text  : the full intervention text shown to the participant

The label is what gets recorded — keep it stable once data collection starts.
"""

INTERVENTIONS = [
    {
        "label": "protein_pro_a",
        "title": "Meat as a protein source",
        "text": (
            "Meat is one of the best sources of protein you can eat. "
            "It contains all the amino acids your body needs, and a small serving of chicken covers a large part of your daily needs. "
            "Most people rely on it to stay strong and energised. "
            "It remains one of the most reliable ways to meet your body's nutritional requirements."
        ),
    },
    {
        "label": "protein_con_a",
        "title": "Plant-based protein alternatives",
        "text": (
            "Many people assume you need meat to get enough protein, but plant foods provide everything your body needs. "
            "Foods like tofu, lentils, and beans contain all the key building blocks. "
            "Many professional athletes perform at the highest level without eating meat. "
            "More and more people are cutting it out and doing just fine."
        ),
    },
    {
        "label": "health_pro_a",
        "title": "Meat in a balanced diet",
        "text": (
            "Not all meat carries the same health risks. "
            "Fish and chicken are widely recognised as part of a healthy, balanced diet. "
            "The main concerns apply to processed meats consumed in large amounts over time. "
            "Most people include meat in their daily diet and stay healthy by eating a good variety and not relying too heavily on any one type."
        ),
    },
    {
        "label": "health_con_a",
        "title": "Health risks of red and processed meat",
        "text": (
            "Eating a lot of red meat or processed meat, like sausages and bacon, can increase the risk of serious illnesses like cancer and heart disease. "
            "The more you eat, the greater the risk. "
            "More and more people are cutting back on these foods, and health guidelines suggest that keeping amounts low is a good idea."
        ),
    },
    {
        "label": "welfare_pro_a",
        "title": "Higher-welfare farming as an alternative",
        "text": (
            "Most concerns about how animals are treated come down to how they are kept on large farms. "
            "Better farms already exist as an alternative. "
            "These farms give animals more space and time outdoors, and are checked each year to make sure they meet the required standards. "
            "Their products are sold in many shops, and more people are choosing them."
        ),
    },
    {
        "label": "welfare_con_a",
        "title": "Animal conditions in meat production",
        "text": (
            "Most pigs and chickens raised for meat never go outside. "
            "They spend their lives in crowded indoor spaces with little room to move. "
            "This is the reality behind most meat sold in shops. "
            "More and more people are becoming aware of these conditions, and many find it difficult to ignore when making decisions about what they eat."
        ),
    },
    {
        "label": "norm_pro_a",
        "title": "Meat as a cultural and family tradition",
        "text": (
            "Meat has been part of most food cultures for generations. "
            "Family recipes, celebrations, and shared meals are built around it. "
            "For most people, eating meat is a natural part of daily life that they have never questioned. "
            "It is simply part of how they were raised, and that remains true for most families today."
        ),
    },
    {
        "label": "norm_con_a",
        "title": "Shifting norms around meat eating",
        "text": (
            "What people eat has always changed over time, and meat is no exception. "
            "More and more people are eating less meat, and many find that it fits naturally into their everyday food habits. "
            "Plant-based meals have become an increasingly common choice. "
            "What counts as a normal meal is shifting, and many people are eating less meat."
        ),
    },
]
