"""
Content for the demo database (see scripts/seed_demo_db.py): ten hotels, their rooms, facilities, policies,
documents, staff and guests.

Rules this file follows so the data is consistent:
  * Every fact lives in ONE place per hotel (check-in time, phone, cancellation tiers, fees). Policies and
    documents are generated from those fields, so they cannot contradict each other.
  * Exactly one policy per type per hotel, using the policy types the admin portal offers.
  * Only the check-in policy states a check-in time (the refund engine reads the first time it finds).
  * All prices are in US dollars (room rates are stored in USD), so guests never see two currencies.
"""

# ---------------------------------------------------------------------------------------------- people
# Accounts used by the frontend's "Quick Fill Demo Roles" buttons (dev builds only). Keep email + password.
DEMO_PASSWORDS = {"admin": "Admin@123", "owner": "Owner@123", "manager": "Manager@123", "receptionist": "Staff@123", "customer": "Customer@123"}

ADMIN = {"name": "Priya Raman", "email": "admin@hms.com", "phone": "+1 (646) 555-0110"}

OWNERS = {  # key -> person; hotels reference these keys
    "victoria": {"name": "Victoria Hale", "email": "owner@hms.com", "phone": "+1 (212) 555-0147"},  # demo owner
    "carlos": {"name": "Carlos Mendez", "email": "carlos.mendez@mirageresorts.com", "phone": "+1 (305) 555-0161"},
    "colette": {"name": "Colette Laurent", "email": "colette.laurent@royalparisian.fr", "phone": "+33 1 42 68 55 00"},
    "kenji": {"name": "Kenji Sato", "email": "kenji.sato@tokyoskyhaven.jp", "phone": "+81 3 5555 0142"},
    "nikos": {"name": "Nikos Andreadis", "email": "nikos.andreadis@santorinicliffside.gr", "phone": "+30 22860 55101"},
    "wayan": {"name": "Wayan Sukarta", "email": "wayan.sukarta@ubudzenresort.com", "phone": "+62 361 555 0193"},
}

# Registered customers: each also gets a guest record with the same email, so "My Reservations" finds their stays.
# The first one is the demo customer.
CUSTOMERS = [
    ("Marcus Vance", "marcus.vance@techcorp.io", "+1 (415) 555-0134", "US"),
    ("Sophia Carter", "sophia.carter@gmail.com", "+1 (312) 555-0178", "US"),
    ("Elena Dubois", "elena.dubois@orange.fr", "+33 6 12 45 78 90", "FR"),
    ("Julian Thorne", "julian.thorne@outlook.com", "+1 (305) 555-0188", "US"),
    ("Amara Chen", "amara.chen@globalvoyage.sg", "+65 9123 4567", "SG"),
    ("Liam O'Connor", "liam.oconnor@eircom.ie", "+353 87 123 4567", "IE"),
    ("Hannah Becker", "hannah.becker@web.de", "+49 151 2345 6789", "DE"),
    ("Rohan Mehta", "rohan.mehta@infosys.com", "+91 98200 12345", "IN"),
    ("Isabella Rossi", "isabella.rossi@libero.it", "+39 333 123 4567", "IT"),
    ("Daniel Kim", "daniel.kim@naver.com", "+82 10 2345 6789", "KR"),
    ("Olivia Bennett", "olivia.bennett@btinternet.com", "+44 7700 900123", "GB"),
    ("Mateo Alvarez", "mateo.alvarez@gmail.com", "+34 612 345 678", "ES"),
    ("Chloe Martin", "chloe.martin@icloud.com", "+1 (617) 555-0142", "US"),
    ("Yuki Tanaka", "yuki.tanaka@docomo.ne.jp", "+81 90 1234 5678", "JP"),
    ("Noah Williams", "noah.williams@yahoo.com", "+1 (206) 555-0193", "US"),
    ("Ava Thompson", "ava.thompson@gmail.com", "+61 412 345 678", "AU"),
    ("Lucas Moreau", "lucas.moreau@free.fr", "+33 6 98 76 54 32", "FR"),
    ("Fatima Al-Sayed", "fatima.alsayed@emirates.net.ae", "+971 50 123 4567", "AE"),
    ("Ethan Brooks", "ethan.brooks@protonmail.com", "+1 (512) 555-0127", "US"),
    ("Sofia Petrova", "sofia.petrova@mail.ru", "+7 916 123 4567", "RU"),
    ("Grace Liu", "grace.liu@hsbc.com.hk", "+852 9123 4567", "HK"),
    ("James Whitaker", "james.whitaker@barclays.co.uk", "+44 7700 900456", "GB"),
    ("Camila Santos", "camila.santos@uol.com.br", "+55 11 91234 5678", "BR"),
    ("Arjun Nair", "arjun.nair@gmail.com", "+91 99860 54321", "IN"),
]

# Guests who booked by phone, email or a travel agent and have no website account.
WALK_IN_GUESTS = [
    ("Robert Hayes", "US"), ("Margaret Collins", "GB"), ("Thomas Schneider", "DE"), ("Ingrid Larsen", "NO"),
    ("Kwame Mensah", "GH"), ("Mei Wong", "HK"), ("Pierre Lefebvre", "FR"), ("Aisha Khan", "PK"),
    ("Diego Fernandez", "MX"), ("Emma Johansson", "SE"), ("Haruto Suzuki", "JP"), ("Laura Bianchi", "IT"),
    ("Samuel Okafor", "NG"), ("Nina Kowalski", "PL"), ("Oliver Grant", "AU"), ("Zara Ahmed", "AE"),
    ("William Foster", "US"), ("Ana Costa", "PT"), ("Ji-woo Park", "KR"), ("Henrik Nielsen", "DK"),
    ("Victoria Adams", "CA"), ("Ravi Shankar", "IN"), ("Charlotte Dupont", "BE"), ("Benjamin Cole", "US"),
    ("Lucia Romero", "AR"), ("Ahmed Hassan", "EG"), ("Freya Andersen", "DK"), ("Kenneth Ong", "SG"),
]

# Name pools for generated one-time guests: (country code, first names, last names, email domains).
NAME_POOLS = [
    ("US", ["James", "Mary", "Robert", "Jennifer", "Michael", "Linda", "David", "Susan", "Kevin", "Ashley", "Brian", "Megan", "Ryan", "Lauren"],
     ["Smith", "Johnson", "Brown", "Miller", "Davis", "Wilson", "Anderson", "Taylor", "Moore", "Jackson", "Harris", "Clark", "Lewis", "Walker"],
     ["gmail.com", "yahoo.com", "outlook.com", "icloud.com"]),
    ("GB", ["Oliver", "Amelia", "Harry", "Isla", "George", "Emily", "Jack", "Sophie", "Henry", "Lucy"],
     ["Taylor", "Evans", "Roberts", "Wright", "Hughes", "Green", "Hall", "Wood", "Turner", "Cooper"], ["btinternet.com", "gmail.com", "outlook.com"]),
    ("FR", ["Louis", "Chloé", "Gabriel", "Léa", "Arthur", "Manon", "Jules", "Camille", "Hugo", "Inès"],
     ["Martin", "Bernard", "Petit", "Durand", "Leroy", "Moreau", "Simon", "Laurent", "Michel", "Garcia"], ["orange.fr", "free.fr", "gmail.com"]),
    ("DE", ["Lukas", "Anna", "Felix", "Lena", "Paul", "Marie", "Jonas", "Laura", "Leon", "Mia"],
     ["Müller", "Schmidt", "Fischer", "Weber", "Wagner", "Becker", "Hoffmann", "Koch", "Richter", "Klein"], ["web.de", "gmx.de", "gmail.com"]),
    ("JP", ["Haruto", "Yui", "Sota", "Hina", "Ren", "Aoi", "Riku", "Sakura", "Kaito", "Mei"],
     ["Sato", "Suzuki", "Takahashi", "Tanaka", "Watanabe", "Ito", "Nakamura", "Kobayashi", "Kato", "Yoshida"], ["docomo.ne.jp", "gmail.com", "yahoo.co.jp"]),
    ("IN", ["Aarav", "Ananya", "Vihaan", "Diya", "Arjun", "Isha", "Kabir", "Saanvi", "Rohan", "Priya"],
     ["Sharma", "Patel", "Gupta", "Iyer", "Reddy", "Nair", "Kapoor", "Singh", "Joshi", "Menon"], ["gmail.com", "outlook.com", "rediffmail.com"]),
    ("AU", ["Jack", "Charlotte", "William", "Olivia", "Noah", "Ava", "Thomas", "Grace"],
     ["Kelly", "Ryan", "Murphy", "Campbell", "Mitchell", "Stewart", "Morris", "Bell"], ["bigpond.com", "gmail.com"]),
    ("BR", ["Miguel", "Helena", "Arthur", "Alice", "Davi", "Laura", "Bernardo", "Valentina"],
     ["Silva", "Santos", "Oliveira", "Souza", "Lima", "Pereira", "Costa", "Rodrigues"], ["uol.com.br", "gmail.com"]),
    ("IT", ["Leonardo", "Sofia", "Francesco", "Giulia", "Alessandro", "Aurora", "Lorenzo", "Ginevra"],
     ["Rossi", "Russo", "Ferrari", "Esposito", "Romano", "Colombo", "Ricci", "Marino"], ["libero.it", "gmail.com"]),
    ("CN", ["Wei", "Fang", "Hao", "Jing", "Lei", "Xin", "Yang", "Min"],
     ["Wang", "Li", "Zhang", "Liu", "Chen", "Yang", "Huang", "Zhao"], ["qq.com", "163.com", "gmail.com"]),
    ("AE", ["Omar", "Layla", "Khalid", "Noura", "Hamad", "Mariam", "Saeed", "Aisha"],
     ["Al Maktoum", "Al Nahyan", "Al Mansouri", "Al Shamsi", "Al Ketbi", "Al Falasi"], ["emirates.net.ae", "gmail.com"]),
    ("MX", ["Santiago", "Valeria", "Mateo", "Regina", "Emiliano", "Ximena", "Diego", "Camila"],
     ["Hernández", "García", "Martínez", "López", "González", "Pérez", "Sánchez", "Ramírez"], ["gmail.com", "hotmail.com"]),
]

# First names for travel companions (spouses, friends, children) added to a booking.
COMPANION_FIRST_NAMES = ["Anna", "David", "Sarah", "Michael", "Emily", "Leo", "Mia", "Lucas", "Zoe", "Ben",
                         "Clara", "Sam", "Nora", "Max", "Ella", "Theo", "Ruby", "Jack", "Lily", "Adam"]

SPECIAL_REQUESTS = [
    "Arriving late, around 11 PM.", "Celebrating our wedding anniversary.", "High floor if possible.",
    "Quiet room away from the elevator, please.", "Early check-in requested if the room is ready.",
    "Allergic to feather pillows; hypoallergenic bedding please.", "Travelling for a birthday; a small cake would be lovely.",
    "Please arrange an airport transfer on arrival.", "Two separate beds if available.", "Gluten-free breakfast options needed.",
]

# ---------------------------------------------------------------------------------------------- hotels
# cancellation: list of (minimum notice in hours, refund %) from most to least notice; anything shorter than the last
# tier (and no-shows) is non-refundable.
HOTELS = [
    {
        "key": "alpine",
        "name": "Alpine Peak Lodge & Ski Resort",
        "address_line1": "750 Mountain View Drive", "city": "Aspen", "state": "CO", "country": "USA", "postal_code": "81611",
        "latitude": 39.18690, "longitude": -106.81860,
        "phone": "+1 (970) 555-0144", "email": "stays@alpinepeaklodge.com", "owner": "victoria",
        "description": "Ski-in/ski-out lodge at the base of Aspen Mountain with heated outdoor mineral baths, stone fireplace "
                       "lounges, a whiskey bar and an alpine wellness spa.",
        "checkin": "4:00 PM", "checkout": "11:00 AM", "timezone": "Mountain Time",
        "checkin_extra": "Ski lockers and the ski valet are available from 8:00 AM on arrival day so guests can ski before their "
                         "room is ready. Late check-out until 1:00 PM can be requested at the front desk, subject to availability.",
        "cancellation": [(72, 100), (24, 50)],
        "room_types": [
            {"name": "Pine Forest King Room", "price": 260, "guests": 2, "rooms": ["201", "202", "203", "204", "205"], "floor_from_number": True,
             "description": "Mountain-modern king room overlooking the evergreen forest, with heated stone floors and a rain shower."},
            {"name": "Chalet Mountain View Suite", "price": 460, "guests": 3, "rooms": ["301", "302", "303"], "floor_from_number": True,
             "description": "Cedar-panelled suite with a wood-burning fireplace, king bed plus day bed, and views of the summit.",
             "amenities": ["Wood-Burning Fireplace"]},
            {"name": "Timber Chalet Sauna Suite", "price": 640, "guests": 4, "rooms": ["CH-1", "CH-2"], "floor": 1,
             "description": "Free-standing two-bedroom timber chalet with a private cedar sauna and direct access to the ski run.",
             "amenities": ["Private Cedar Sauna", "Ski-Run Access Door"]},
        ],
        "amenities": ["Ski-in / Ski-out Mountain Access", "Ski Valet & Heated Boot Lockers", "Heated Outdoor Mineral Baths",
                      "Fireplace Lounge & Whiskey Bar", "The Summit Hearth Restaurant", "Alpine Wellness Spa"],
        "policies": {
            "pet_policy": "Pets are not allowed at Alpine Peak Lodge, to keep rooms hypoallergenic and protect mountain wildlife. Certified service animals are welcome.",
            "pool_and_spa": "The heated outdoor mineral baths and hot tubs are open daily from 8:00 AM to 10:30 PM; robes and towels are provided at the pool chalet. The Alpine Wellness Spa is open from 9:00 AM to 8:00 PM; treatments should be booked a day ahead.",
            "quiet_hours": "Quiet hours are from 9:30 PM to 6:30 AM, so guests can rest before early ski runs. Please carry ski boots rather than wearing them in residential corridors.",
            "parking_valet": "Heated underground valet parking costs $50 per night, including overnight pre-heating, snow clearing and electric-vehicle charging.",
            "deposit_security": "A credit card and photo ID are required on arrival. An incidental hold of $150 per night is placed and released after the room is inspected at departure.",
            "smoking_policy": "The lodge is entirely smoke-free, including balconies and chalets. A $300 cleaning fee applies to any violation.",
            "breakfast_dining": "A mountain breakfast buffet is served daily from 6:30 AM to 10:00 AM at The Summit Hearth for $32 per adult; children under 10 eat free. Dinner is served from 5:30 PM to 10:00 PM and reservations are recommended.",
            "children_extra_beds": "Children aged 10 and under stay free when using existing bedding. Cribs are free on request, and a rollaway cot can be added in Chalet Mountain View Suites for $40 per night.",
        },
        "documents": [
            {"title": "Ski Valet & Equipment Guide 2026-27", "category": "amenity", "access_level": "public", "text":
             "ALPINE PEAK LODGE - SKI VALET & EQUIPMENT GUIDE (2026-27 WINTER SEASON)\n\n"
             "Ski valet\nThe ski valet on the Mountain Terrace level operates daily from 8:00 AM to 6:00 PM. Skis and boots are dried and warmed overnight free of charge for all registered guests. Each room has a heated boot locker opened with the room key card.\n\n"
             "Equipment rental (per day)\n- Standard carving package (Rossignol skis, boots, poles): $65\n- High-performance powder package (Stöckli or Black Crows): $95\n- Junior package (ages 12 and under): $35\n- Helmet rental: $15\nRentals for three days or more receive a 10% discount.\n\n"
             "Lift tickets and lessons\nLift tickets can be bought at the concierge desk and charged to the room. Private lessons with Aspen Snowmass instructors start at $450 for a half day; book at least 48 hours ahead in peak weeks."},
            {"title": "Front Office Night Procedures", "category": "policies", "access_level": "staff_only", "text":
             "STAFF ONLY - Alpine Peak Lodge front office, night shift\n\nThe night auditor closes the day at 2:00 AM and prints the arrivals list for the morning team. Guests arriving after midnight receive pre-encoded key cards from the night safe; the safe code is changed every Monday and is given to staff in person only. Snow emergencies are escalated to the duty manager on extension 900."},
        ],
        "review_highlights": [
            "the ski-in/ski-out access straight onto Aspen Mountain is unbeatable",
            "the ski valet had our boots warm and skis waiting every morning",
            "soaking in the outdoor mineral baths while snow was falling was magical",
            "the private cedar sauna in the Timber Chalet was perfect after a long day on the slopes",
            "the breakfast buffet at The Summit Hearth gave us plenty of fuel for skiing",
            "the fireplace lounge and whiskey bar were the perfect après-ski spot",
            "the staff arranged our lift tickets and lessons without any fuss",
            "our Chalet suite with its wood-burning fireplace was incredibly cosy",
            "the heated underground parking meant no scraping ice off the car",
        ],
        "review_gripes": [
            "dinner at The Summit Hearth gets busy, so book well ahead",
            "the corridors can be noisy when ski groups head out early",
            "the Pine Forest King rooms are on the small side for all our gear",
            "breakfast at $32 per person feels pricey",
        ],
        "staff": {"manager": ("Daniel Brooks", "manager@hms.com"),  # demo manager
                  "receptionists": [("Emily Parker", "staff@hms.com"), ("Tyler Nguyen", "tyler.nguyen@alpinepeaklodge.com")]},
        "media": {"hotel": ["photo-1542601906990-b4d3fb778b09", "photo-1551524559-8af4e6624178", "photo-1502784444187-359ac186c5bb"],
                  "Pine Forest King Room": "photo-1517048676732-d65bc937f952", "Chalet Mountain View Suite": "photo-1584132967334-10e028bd69f7"},
    },
    {
        "key": "biscayne",
        "name": "Biscayne Bay Marina & Yacht Sanctuary",
        "address_line1": "400 Brickell Key Drive", "city": "Miami", "state": "FL", "country": "USA", "postal_code": "33131",
        "latitude": 25.76820, "longitude": -80.18640,
        "phone": "+1 (305) 555-0122", "email": "dockmaster@biscaynebayhotel.com", "owner": "victoria",
        "description": "Harbourfront hotel on Brickell Key with its own deep-water marina, a rooftop saltwater infinity pool, "
                       "a helipad and sunset cocktail terraces over Biscayne Bay.",
        "checkin": "4:00 PM", "checkout": "12:00 PM (noon)", "timezone": "Eastern Time",
        "checkin_extra": "Guests arriving by boat can check in at the harbour master's office 24 hours a day.",
        "cancellation": [(72, 100), (36, 50)],
        "room_types": [
            {"name": "Harbor View King", "price": 310, "guests": 2, "rooms": ["1201", "1202", "1203", "1204"], "floor_from_number": True,
             "description": "King room on the 12th floor with floor-to-ceiling windows over the marina and Biscayne Bay."},
            {"name": "Biscayne Skyline Master Suite", "price": 440, "guests": 2, "rooms": ["2501", "2502", "2503"], "floor_from_number": True,
             "description": "25th-floor suite with sweeping bay and skyline views, an oversized king bed and a private cocktail lounge."},
            {"name": "Marina Yacht Panorama Villa", "price": 720, "guests": 4, "rooms": ["MAR-01", "MAR-02"], "floor": 1,
             "description": "Two-level waterfront villa with a private dock gangway, sundeck and two bedrooms.",
             "amenities": ["Private Dock Gangway"]},
        ],
        "amenities": ["Private Marina & Yacht Charters", "Rooftop Saltwater Infinity Pool", "Hydrotherapy Spa & Cold Plunge",
                      "Helipad & Chauffeured Airport Service", "Mediterranean Grill", "Sunset Cocktail Terrace"],
        "policies": {
            "pet_policy": "Pets are not allowed in suites or on the marina docks because of port security rules. Certified service dogs are welcome.",
            "pool_and_spa": "The rooftop saltwater infinity pool and hot tub are open from 8:00 AM to 10:00 PM. The hydrotherapy spa and cold plunge are open from 9:00 AM to 9:00 PM.",
            "quiet_hours": "Quiet hours are from 10:00 PM to 7:00 AM. Boat engines and loud music on the docks are not permitted during these hours.",
            "parking_valet": "Valet parking costs $48 per night. Secure self-parking for cars and boat trailers costs $35 per night.",
            "deposit_security": "A credit card and photo ID are required on arrival. An incidental hold of $200 per night is placed and released after departure.",
            "smoking_policy": "All rooms, villas and docks are smoke-free. A $350 cleaning fee applies to any violation; smoking is permitted only at the marked area by the harbour master's office.",
            "breakfast_dining": "Breakfast is served at The Anchorage from 6:30 AM to 10:30 AM ($29 per adult). The Mediterranean Grill serves dinner from 6:00 PM to 11:00 PM.",
            "children_extra_beds": "Children under 12 stay free using existing bedding. Life jackets in all sizes can be borrowed from the harbour master. Cribs are free; extra beds are available only in Marina Yacht Panorama Villas.",
        },
        "documents": [
            {"title": "Marina & Yacht Charter Guide", "category": "amenity", "access_level": "public", "text":
             "BISCAYNE BAY MARINA - GUEST GUIDE\n\n"
             "Transient slips\nDeep-water slips for yachts up to 120 feet cost $6 per foot per night, with shore power (up to 480V three-phase), fresh water and pump-out included. Reserve with the harbour master at least 48 hours ahead.\n\n"
             "Charters\nOur 65-foot motor yacht can be chartered for a four-hour sunset cruise for $2,400 (up to 12 guests, captain and crew included). Fishing charters start at $1,100 for a half day.\n\n"
             "Helicopter transfers\nHelicopter transfers between Miami International Airport and our helipad take about 10 minutes and cost $1,850 per flight (up to 4 passengers). Book 24 hours ahead through the concierge."},
            {"title": "Dock Security Procedures", "category": "policies", "access_level": "staff_only", "text":
             "STAFF ONLY - Biscayne Bay Marina dock security\n\nVisitor vessels must be logged by the harbour master before mooring. Dock gate codes rotate weekly and are never shared with guests by phone. Any fuel spill is reported immediately to the duty engineer on extension 450 and to the US Coast Guard."},
        ],
        "review_highlights": [
            "watching the yachts come in from our balcony was so peaceful",
            "the sunset charter on the 65-foot yacht was the highlight of our year",
            "the rooftop infinity pool overlooking the bay at twilight is spectacular",
            "breakfast at The Anchorage with Cuban coffee was excellent",
            "the helicopter transfer from the airport took ten minutes and was unforgettable",
            "the harbour master made docking our own boat completely effortless",
            "the Mediterranean Grill served the best seafood we had in Miami",
            "it is close to the city yet away from the party crowds",
        ],
        "review_gripes": [
            "valet parking was slow on Saturday evening",
            "the rooftop pool gets crowded on weekends",
            "check-out at noon came too soon",
        ],
        "staff": {"manager": ("Gabriela Ortiz", "gabriela.ortiz@biscaynebayhotel.com"),
                  "receptionists": [("Marcus Reed", "marcus.reed@biscaynebayhotel.com"), ("Lina Haddad", "lina.haddad@biscaynebayhotel.com")]},
        "media": {"hotel": ["photo-1567684014761-b65e2e59b9eb", "photo-1544551763-46a013bb70d5"],
                  "Biscayne Skyline Master Suite": "photo-1512917774080-9991f1c4c750"},
    },
    {
        "key": "paris",
        "name": "Royal Parisian Boutique Hotel",
        "address_line1": "12 Rue de la Paix", "city": "Paris", "state": "Île-de-France", "country": "France", "postal_code": "75002",
        "latitude": 48.86930, "longitude": 2.33120,
        "phone": "+33 1 44 55 01 23", "email": "bonjour@royalparisian.fr", "owner": "colette",
        "description": "Boutique Haussmann townhouse between Place Vendôme and the Opéra Garnier, with a glass-domed courtyard, "
                       "a spa grotto and a sommelier's wine cellar.",
        "checkin": "2:00 PM", "checkout": "12:00 PM (noon)", "timezone": "Central European Time",
        "checkin_extra": "Late check-out until 3:00 PM is complimentary for guests who booked directly with the hotel.",
        "cancellation": [(48, 100), (24, 50)],
        "room_types": [
            {"name": "Classic Haussmann Deluxe", "price": 310, "guests": 2, "rooms": ["201", "202", "203", "301", "302"], "floor_from_number": True,
             "description": "Elegant room with high moulded ceilings, herringbone parquet floors and a marble bathroom."},
            {"name": "Vendôme Executive King", "price": 390, "guests": 2, "rooms": ["401", "402", "403"], "floor_from_number": True,
             "description": "Contemporary king room with a private reading library and a Nespresso bar."},
            {"name": "Eiffel Romance Suite", "price": 520, "guests": 2, "rooms": ["501", "502"], "floor_from_number": True,
             "description": "Top-floor suite with a wrought-iron balcony over the zinc rooftops, silk wall hangings and a clawfoot bath; the Eiffel Tower is visible in the distance.",
             "amenities": ["Private Balcony", "Clawfoot Bathtub"]},
        ],
        "amenities": ["Glass-Domed Courtyard Breakfast Salon", "Romanesque Spa Grotto", "Sommelier Wine & Champagne Cellar",
                      "Chauffeured Airport Transfers", "Opera & Theatre Concierge"],
        "policies": {
            "pet_policy": "Dogs and cats up to 25 lbs are welcome at no extra charge, with a pet bed and water bowls provided. Please let us know when booking.",
            "pool_and_spa": "The hotel has no swimming pool. The Romanesque Spa Grotto is open from 8:00 AM to 9:00 PM for hotel guests; 60-minute private hydrotherapy sessions cost $95 and must be reserved.",
            "quiet_hours": "Quiet hours are from 10:30 PM to 7:30 AM. All windows are double-glazed against street noise.",
            "parking_valet": "The secure underground courtyard garage has limited spaces at $60 per night and must be reserved in advance. Valet service is included.",
            "deposit_security": "A credit card and photo ID are required on arrival. An incidental hold of $150 per night is placed and released after departure.",
            "smoking_policy": "The hotel is smoke-free, including balconies. A $250 cleaning fee applies to any violation.",
            "breakfast_dining": "Breakfast is served in the glass-domed courtyard from 7:00 AM to 11:00 AM for $40 per adult, with croissants from a local boulangerie and Mariage Frères teas.",
            "children_extra_beds": "One child under 6 stays free. Baby cots are free; babysitting costs $28 per hour and needs 24 hours' notice. Rooms cannot take extra beds.",
        },
        "documents": [
            {"title": "Guest Services Guide", "category": "faq", "access_level": "public", "text":
             "ROYAL PARISIAN - GUEST SERVICES\n\n"
             "Airport transfers\nA chauffeured Mercedes S-Class meets guests at Charles de Gaulle for $175 one way, or Orly for $130 one way. Book at least 24 hours ahead.\n\n"
             "Concierge\nOur concierge books opera and ballet tickets at the Opéra Garnier (a 5-minute walk), restaurant tables and private museum tours, including early-entry Louvre visits.\n\n"
             "Wine cellar\nThe master sommelier hosts a champagne tasting every Thursday and Saturday at 6:00 PM for $65 per person.\n\n"
             "Wi-Fi\nFree high-speed Wi-Fi is available throughout the hotel; the network is RoyalParisian-Guest."},
        ],
        "review_highlights": [
            "breakfast under the glass dome with warm croissants was idyllic",
            "the concierge secured impossible dinner reservations with ease",
            "our balcony over the Paris rooftops was something we will never forget",
            "the spa grotto was heavenly after walking all day",
            "we walked to the Opéra Garnier in five minutes",
            "the rooms are completely quiet despite the city outside",
            "the champagne tasting in the cellar was a lovely surprise",
            "they welcomed our little dog like a guest of honour",
        ],
        "review_gripes": [
            "the Classic Deluxe room was smaller than the photos suggested",
            "the lift is tiny, as in most Paris townhouses",
            "garage spaces are limited, so reserve ahead",
        ],
        "staff": {"manager": ("Antoine Mercier", "antoine.mercier@royalparisian.fr"),
                  "receptionists": [("Camille Girard", "camille.girard@royalparisian.fr"), ("Hugo Lambert", "hugo.lambert@royalparisian.fr")]},
        "media": {"hotel": ["photo-1502602898657-3e91760cbb34", "photo-1551882547-ff40c63fe5fa"],
                  "Classic Haussmann Deluxe": "photo-1590490360182-c33d57733427", "Eiffel Romance Suite": "photo-1566665797739-1674de7a421a"},
    },
    {
        "key": "santorini",
        "name": "Santorini Cliffside Suites & Caldera Spa",
        "address_line1": "Oia Caldera Walkway", "city": "Santorini", "state": "South Aegean", "country": "Greece", "postal_code": "84702",
        "latitude": 36.46180, "longitude": 25.37530,
        "phone": "+30 22860 55100", "email": "sunset@santorinicliffside.gr", "owner": "nikos",
        "description": "Whitewashed cave suites carved into the cliffs of Oia, each with a private heated plunge pool facing "
                       "the caldera and the famous sunset, plus a spa set in natural lava rock.",
        "checkin": "3:00 PM", "checkout": "11:00 AM", "timezone": "Eastern European Time",
        "checkin_extra": "Luggage can be left with our porters from 9:00 AM, and our terrace is open to early arrivals.",
        "cancellation": [(168, 100), (72, 50)],
        "room_types": [
            {"name": "Cycladic Cave Junior Suite", "price": 360, "guests": 2, "rooms": ["CJ-1", "CJ-2", "CJ-3", "CJ-4"], "floor": 1,
             "description": "Cave suite with a vaulted whitewashed ceiling, a private terrace and a heated plunge pool."},
            {"name": "Aegean Sunset Villa", "price": 490, "guests": 2, "rooms": ["AV-1", "AV-2", "AV-3"], "floor": 2,
             "description": "Sun-drenched villa with a Cycladic terrace and daybed, a marble bath and a heated plunge pool facing the sunset."},
            {"name": "Caldera Infinity Cave Suite", "price": 750, "guests": 2, "rooms": ["CS-1", "CS-2"], "floor": 3,
             "description": "Our signature cave suite opening onto a heated infinity pool directly above the volcanic caldera."},
        ],
        "amenities": ["Private Heated Plunge Pools", "Lava-Rock Cave Spa", "Caldera Sunset Terrace Bar",
                      "Breakfast Served on Your Terrace", "Airport & Port Transfers"],
        "policies": {
            "pet_policy": "Pets cannot be accommodated because the suites are reached by steep cliffside steps. Service animals are welcome by prior arrangement.",
            "pool_and_spa": "Every suite has its own plunge pool heated to 86°F all year. The lava-rock cave spa is open from 10:00 AM to 8:00 PM; a 60-minute massage costs $140.",
            "quiet_hours": "Quiet hours are from 11:00 PM to 8:00 AM to respect neighbouring terraces.",
            "parking_valet": "Oia's caldera path is car-free. Free guest parking is available at the Oia main car park, 400 metres away, and our porters carry luggage to your suite at no charge.",
            "deposit_security": "A credit card and photo ID are required on arrival. An incidental hold of $200 per night is placed and released after departure.",
            "smoking_policy": "Suites and pools are smoke-free. Smoking is allowed only on the shared Sunset Terrace Bar. A $250 cleaning fee applies to any violation.",
            "breakfast_dining": "Breakfast is included and served on your private terrace between 7:30 AM and 11:00 AM. The Sunset Terrace Bar serves light dinners from 6:00 PM to 11:00 PM.",
            "children_extra_beds": "The suites are designed for two adults; children aged 12 and over are welcome. Extra beds cannot be added.",
        },
        "documents": [
            {"title": "Arrival & Island Guide", "category": "faq", "access_level": "public", "text":
             "SANTORINI CLIFFSIDE - ARRIVAL & ISLAND GUIDE\n\n"
             "Getting here\nOur driver meets guests at Santorini airport (25 minutes, $50 one way) or Athinios port (40 minutes, $60 one way). Book at least 48 hours ahead.\n\n"
             "Arrival\nThe last 400 metres are a pedestrian path with steps; our porters carry all luggage.\n\n"
             "Sunset\nThe sun sets over the caldera between 6:00 PM (winter) and 8:45 PM (summer). The Sunset Terrace Bar reserves tables for in-house guests.\n\n"
             "Cave spa menu\nLava-stone massage (60 minutes) $140; Aegean salt scrub (45 minutes) $95; couples' ritual (90 minutes) $320."},
        ],
        "review_highlights": [
            "the private heated plunge pool facing the caldera exceeded our dreams",
            "breakfast delivered to our terrace every morning was a joy",
            "watching the Oia sunset from our own terrace was magical",
            "the cave spa in natural lava rock is an architectural wonder",
            "the porters carried every bag up the steps without a word of complaint",
            "the airport pick-up was smooth and the driver gave great island tips",
            "the suites are pristine, minimalist and wonderfully calm",
        ],
        "review_gripes": [
            "the steps are steep, so pack light",
            "the path outside gets crowded with sunset visitors",
            "dinner options at the hotel are limited",
        ],
        "staff": {"manager": ("Eleni Papadakis", "eleni.papadakis@santorinicliffside.gr"),
                  "receptionists": [("Giorgos Nikolaidis", "giorgos.nikolaidis@santorinicliffside.gr"), ("Maria Kostaki", "maria.kostaki@santorinicliffside.gr")]},
        "media": {"hotel": ["photo-1570077188670-e3a8d69ac5ff", "photo-1469854523086-cc02fe5d8800", "photo-1533105079780-92b9be482077"],
                  "Aegean Sunset Villa": "photo-1515542622106-78bda8ba0e5b"},
    },
    {
        "key": "mirage",
        "name": "The Grand Mirage Resort & Spa",
        "address_line1": "1200 Ocean Drive", "city": "Miami Beach", "state": "FL", "country": "USA", "postal_code": "33139",
        "latitude": 25.78260, "longitude": -80.13000,
        "phone": "+1 (305) 555-0199", "email": "concierge@grandmirage.com", "owner": "carlos",
        "description": "Oceanfront resort on Ocean Drive with a heated infinity pool, a lagoon, private beach cabanas, "
                       "an Ayurvedic spa and 24-hour in-suite dining.",
        "checkin": "3:00 PM", "checkout": "11:00 AM", "timezone": "Eastern Time",
        "checkin_extra": "Early arrivals can store luggage and use the pool and beach from 9:00 AM. Presidential Penthouse guests may check out as late as 4:00 PM, subject to availability.",
        "cancellation": [(48, 100), (24, 50)],
        "room_types": [
            {"name": "Tropical Garden Villa", "price": 290, "guests": 2, "rooms": ["G-01", "G-02", "G-03", "G-04"], "floor": 1,
             "description": "Secluded garden villa among the palms with a private terrace, hammock and outdoor shower. The only rooms that accept pets."},
            {"name": "Deluxe Coral King Suite", "price": 380, "guests": 2, "rooms": ["401", "402", "403", "501", "502"], "floor_from_number": True,
             "description": "Art Deco king suite with floor-to-ceiling glass, an Italian marble bathroom and a rainfall soaking tub."},
            {"name": "Presidential Oceanfront Penthouse", "price": 850, "guests": 4, "rooms": ["PH-1", "PH-2"], "floor": 12,
             "description": "Top-floor two-bedroom penthouse with a wrap-around balcony, private infinity jacuzzi and butler bar.",
             "amenities": ["24/7 Personal Butler", "Private Infinity Jacuzzi"]},
        ],
        "amenities": ["Heated Infinity Ocean Pool & Lagoon", "Lotus Ayurvedic Spa", "Private Beach Cabanas",
                      "24-Hour In-Suite Dining", "Valet Parking & EV Charging", "Coral Bistro"],
        "policies": {
            "pet_policy": "Dogs and cats up to 35 lbs are welcome in Tropical Garden Villas only, for $40 per night. Pets must be leashed in public gardens.",
            "pool_and_spa": "The infinity pool and lagoon are open from 7:00 AM to 10:00 PM. The Lotus Ayurvedic Spa is open from 8:00 AM to 8:00 PM; aromatherapy and Swedish massages start at $165 for 60 minutes.",
            "quiet_hours": "Quiet hours are from 10:00 PM to 7:00 AM across the resort, including balconies.",
            "parking_valet": "Valet parking costs $45 per night with unlimited in-and-out privileges. Electric-vehicle charging is free for staying guests.",
            "deposit_security": "A credit card and photo ID are required on arrival. An incidental hold of $150 per night is placed and released after departure.",
            "smoking_policy": "The resort is smoke-free, including vaping on balconies. A $350 cleaning fee applies to any violation.",
            "breakfast_dining": "A complimentary breakfast is served at Coral Bistro from 6:30 AM to 10:30 AM. In-suite dining is available 24 hours a day; a 20% service charge applies.",
            "children_extra_beds": "Children aged 12 and under stay free using existing bedding. Cribs are free, and rollaway beds cost $45 per night in Deluxe Coral King Suites and Penthouses.",
        },
        "documents": [
            {"title": "Cabana & Pool Guide 2026", "category": "amenity", "access_level": "public", "text":
             "THE GRAND MIRAGE - CABANA & POOL GUIDE 2026\n\n"
             "Beach cabanas\nPrivate oceanfront cabanas are available from 8:00 AM to 8:00 PM. A full-day rental costs $250 on weekdays and $350 on weekends and includes a tropical fruit platter, chilled water and a dedicated attendant. Cabanas can be reserved up to 48 hours in advance through the pool desk or the AI concierge. Cancel at least 12 hours before your reservation to avoid a 50% charge.\n\n"
             "Pool rules\nThe infinity pool is heated to 82°F all year. Children under 14 must be accompanied by an adult. Glass is not allowed in the pool area; drinks are served in polycarbonate glassware. Sunscreen (SPF 30 and 50) is free at the towel pavilion."},
            {"title": "In-Suite Dining Menu", "category": "menu", "access_level": "public", "text":
             "THE GRAND MIRAGE - IN-SUITE DINING (24 HOURS)\nDial 404 from your room. A 20% service charge applies to all in-suite orders. Gluten-free, vegan and kosher dishes are available on request.\n\n"
             "Pan-seared Chilean sea bass with saffron risotto - $54\nPrime Wagyu ribeye (12 oz) with truffle mash - $78\nHeirloom tomato and burrata salad - $26\nMidnight truffle burger with parmesan fries - $34\nTropical fruit platter - $22"},
            {"title": "Night Audit & Late Arrival Procedures", "category": "policies", "access_level": "staff_only", "text":
             "STAFF ONLY - The Grand Mirage night operations\n\nGuests arriving after 11:00 PM are met by the night concierge at the porte-cochère. Pre-encoded keys and registration packs are prepared by the night auditor before midnight. Cabana deposits for the next day are reconciled at 1:00 AM. Security incidents go to the duty manager on extension 777."},
        ],
        "review_highlights": [
            "the oceanfront infinity pool made our anniversary unforgettable",
            "the private cabanas made us feel like royalty",
            "the Lotus spa massage reset my entire nervous system",
            "breakfast at Coral Bistro had the best eggs Benedict",
            "the penthouse butler thought of everything",
            "our dog loved the garden villa as much as we did",
            "free EV charging on site was super convenient",
            "the midnight truffle burger from in-suite dining was a guilty pleasure",
        ],
        "review_gripes": [
            "cabanas book up fast on weekends, so reserve early",
            "the 20% service charge on in-suite dining adds up",
            "the lobby can be busy at check-in time",
        ],
        "staff": {"manager": ("Sofia Ramirez", "sofia.ramirez@grandmirage.com"),
                  "receptionists": [("Jordan Lee", "jordan.lee@grandmirage.com"), ("Natalia Cruz", "natalia.cruz@grandmirage.com")]},
        "media": {"hotel": ["photo-1571003123894-1f0594d2b5d9", "photo-1540541338287-41700207dee6", "photo-1520250497591-112f2f40a3f4"],
                  "Deluxe Coral King Suite": "photo-1582719478250-c89cae4dc85b"},
    },
    {
        "key": "manhattan",
        "name": "The Manhattan Skyline Palace & Residences",
        "address_line1": "112 Central Park South", "city": "New York", "state": "NY", "country": "USA", "postal_code": "10019",
        "latitude": 40.76550, "longitude": -73.97760,
        "phone": "+1 (212) 555-0100", "email": "butler@manhattanskylinepalace.com", "owner": "victoria",
        "description": "Central Park South tower hotel on floors 30 to 48, combining Gilded Age style with penthouse views, "
                       "a skyline wellness floor and 24-hour white-glove concierge service.",
        "checkin": "3:00 PM", "checkout": "12:00 PM (noon)", "timezone": "Eastern Time",
        "checkin_extra": "Early check-in from 10:00 AM can be guaranteed for $150 if requested when booking.",
        "cancellation": [(48, 100), (24, 50)],
        "room_types": [
            {"name": "Fifth Avenue Deluxe Queen", "price": 395, "guests": 2, "rooms": ["3201", "3202", "3203", "3204"], "floor_from_number": True,
             "description": "Queen room on the 32nd floor with acoustic glass, a marble bathroom and city views."},
            {"name": "Manhattan Premier King", "price": 480, "guests": 2, "rooms": ["3601", "3602", "3603"], "floor_from_number": True,
             "description": "High-ceilinged king room with a marble fireplace, acoustic glass and hand-woven silk carpets."},
            {"name": "Central Park Tower Suite", "price": 920, "guests": 2, "rooms": ["4801", "4802"], "floor_from_number": True,
             "description": "48th-floor suite with uninterrupted Central Park views, an Italian limestone bathroom and a private dressing salon.",
             "amenities": ["Private Elevator Access", "Personal Dressing Salon"]},
        ],
        "amenities": ["24-Hour White-Glove Concierge", "Skyline Wellness Floor with Indoor Lap Pool", "The Park Room Restaurant",
                      "Botanical Tea Lounge", "Valet Parking"],
        "policies": {
            "pet_policy": "Dogs up to 25 lbs are welcome in Fifth Avenue Deluxe Queen and Manhattan Premier King rooms for $150 per stay.",
            "pool_and_spa": "The 38th-floor Skyline Wellness Floor, with an indoor saltwater lap pool, sauna and treatment rooms, is open from 6:00 AM to 10:00 PM.",
            "quiet_hours": "Quiet hours are from 11:00 PM to 7:00 AM. The tower's acoustic glass keeps Central Park South traffic out, so please keep in-room music low after 11:00 PM.",
            "parking_valet": "Valet parking costs $85 per night. There is no self-parking.",
            "deposit_security": "A credit card and photo ID are required on arrival. An incidental hold of $250 per night is placed and released after departure.",
            "smoking_policy": "The hotel is smoke-free. A $500 cleaning fee applies to any violation.",
            "breakfast_dining": "The Park Room serves an à la carte breakfast from 6:30 AM to 10:30 AM. Afternoon botanical tea is served in the Tea Lounge from 2:00 PM to 5:00 PM ($58 per person).",
            "children_extra_beds": "Children under 12 stay free. Cribs are free; rooms take a maximum of two adults plus one crib, and no rollaway beds are available.",
        },
        "documents": [
            {"title": "Residence Services Guide", "category": "faq", "access_level": "public", "text":
             "THE MANHATTAN SKYLINE PALACE - RESIDENCE SERVICES\n\n"
             "Transfers\nA chauffeured car to or from JFK costs $195 and to or from LaGuardia $160, one way.\n\n"
             "Concierge\nOur white-glove concierge is available 24 hours a day for theatre and Carnegie Hall tickets (a 4-minute walk), restaurant reservations and private shopping on Fifth Avenue.\n\n"
             "Wellness\nPersonal trainers can be booked on the 38th-floor Skyline Wellness Floor for $140 per hour.\n\n"
             "Tea lounge\nThe Botanical Tea Lounge serves rare single-estate teas and an afternoon tea tasting from 2:00 PM to 5:00 PM."},
        ],
        "review_highlights": [
            "the views over Central Park from the 48th floor at dusk were mesmerising",
            "the white-glove concierge got us Broadway tickets the same day",
            "the botanical afternoon tea was the most refined we have had",
            "we walked to Carnegie Hall in four minutes",
            "the room was completely silent despite being in midtown",
            "the lap pool on the wellness floor was a great way to start the day",
            "private elevator access to our suite felt incredibly exclusive",
        ],
        "review_gripes": [
            "valet parking at $85 a night is steep",
            "breakfast in The Park Room is expensive",
            "the queen rooms are compact by suite standards",
        ],
        "staff": {"manager": ("Rebecca Stein", "rebecca.stein@manhattanskylinepalace.com"),
                  "receptionists": [("Andre Washington", "andre.washington@manhattanskylinepalace.com"), ("Mia Goldberg", "mia.goldberg@manhattanskylinepalace.com")]},
        "media": {"hotel": ["photo-1506744038136-46273834b3fb", "photo-1534430480872-3498386e7856"],
                  "Central Park Tower Suite": "photo-1502672260266-1c1ef2d93688"},
    },
    {
        "key": "mayfair",
        "name": "The Mayfair Heritage Hotel & Club",
        "address_line1": "41 Brook Street", "city": "London", "state": "Greater London", "country": "United Kingdom", "postal_code": "W1K 4HR",
        "latitude": 51.51260, "longitude": -0.14810,
        "phone": "+44 20 7555 0199", "email": "reservations@mayfairheritage.co.uk", "owner": "victoria",
        "description": "Georgian townhouse hotel in Mayfair with a mahogany library, an afternoon tea salon, a members' bar "
                       "and a Savile Row tailoring concierge.",
        "checkin": "2:00 PM", "checkout": "11:00 AM", "timezone": "UK time",
        "checkin_extra": "Luggage can be left with the hall porter from 8:00 AM, and afternoon tea can be booked for your arrival day.",
        "cancellation": [(48, 100), (24, 50)],
        "room_types": [
            {"name": "Mayfair Heritage Deluxe", "price": 380, "guests": 2, "rooms": ["101", "102", "103", "201", "202"], "floor_from_number": True,
             "description": "Classic British room with velvet furnishings, a king bed and Penhaligon's toiletries."},
            {"name": "Savile Row Junior Suite", "price": 520, "guests": 2, "rooms": ["203", "204", "301"], "floor_from_number": True,
             "description": "Junior suite with a drawing room where our tailoring concierge can hold private fittings."},
            {"name": "Royal Mayfair Ambassador Suite", "price": 650, "guests": 2, "rooms": ["401", "402"], "floor_from_number": True,
             "description": "Top-floor suite with a mahogany study, four-poster king bed, heated marble floors and a butler's pantry.",
             "amenities": ["Butler's Pantry", "Four-Poster Bed"]},
        ],
        "amenities": ["Afternoon Tea Salon", "Members' Bar", "Mahogany Library", "Heated Cigar Terrace", "Savile Row Tailoring Concierge"],
        "policies": {
            "pet_policy": "Dogs up to 30 lbs are welcome in Mayfair Heritage Deluxe rooms for $95 per stay, with a bed and bowls provided.",
            "pool_and_spa": "The hotel has no pool or spa. Guests have free access to a partner health club with an indoor pool five minutes' walk away (6:00 AM to 10:00 PM), and in-room massages cost $175 for 60 minutes.",
            "quiet_hours": "Quiet hours are from 11:00 PM to 7:00 AM. The Cigar Terrace closes at 10:30 PM out of respect for neighbouring residences on Brook Street.",
            "parking_valet": "There is no on-site parking. Our valet can park your car in a secure garage nearby for $80 per 24 hours. Central London's congestion charge applies on weekdays.",
            "deposit_security": "A credit card and photo ID are required on arrival. An incidental hold of $150 per night is placed and released after departure.",
            "smoking_policy": "By law, smoking is not allowed indoors. Cigars may be enjoyed on the heated Cigar Terrace. A $300 cleaning fee applies to smoking in rooms.",
            "breakfast_dining": "A full English or continental breakfast is served in the Library from 7:00 AM to 10:30 AM ($38). Afternoon tea is served daily from 2:00 PM to 6:00 PM ($85 per person) and should be reserved.",
            "children_extra_beds": "One child under 12 stays free. Cots are free; extra beds cannot be added.",
        },
        "documents": [
            {"title": "Club Facilities & Etiquette", "category": "faq", "access_level": "public", "text":
             "THE MAYFAIR HERITAGE - CLUB FACILITIES\n\n"
             "Members' Bar\nOpen from 4:00 PM to 1:00 AM, with more than 120 single-malt Scotch whiskies. Smart casual dress is requested after 6:00 PM.\n\n"
             "Library\nThe mahogany library is open to hotel guests all day for reading and quiet work; calls should be taken outside.\n\n"
             "Tailoring\nOur Savile Row tailoring concierge arranges fittings in your suite; a bespoke suit takes about eight weeks and three fittings.\n\n"
             "Getting here\nBond Street station (Elizabeth line and Central line) is a 4-minute walk. A chauffeured car from Heathrow costs $140 one way."},
        ],
        "review_highlights": [
            "the afternoon tea was the best we have had in London",
            "stepping into the mahogany library feels like joining a private club",
            "the members' bar has an extraordinary single-malt collection",
            "the tailoring concierge arranged a fitting in our suite",
            "Bond Street station is a few minutes' walk away",
            "the hall porter remembered our names from day one",
            "the four-poster bed in the Ambassador Suite was wonderfully grand",
        ],
        "review_gripes": [
            "parking in Mayfair is expensive, so come by train",
            "the Heritage Deluxe rooms are on the cosy side",
            "there is no pool on site",
        ],
        "staff": {"manager": ("William Ashford", "william.ashford@mayfairheritage.co.uk"),
                  "receptionists": [("Charlotte Hughes", "charlotte.hughes@mayfairheritage.co.uk"), ("Oliver Patel", "oliver.patel@mayfairheritage.co.uk")]},
        "media": {"hotel": ["photo-1582719508461-905c673771fd"],
                  "Mayfair Heritage Deluxe": "photo-1566665797739-1674de7a421a", "Royal Mayfair Ambassador Suite": "photo-1590381105924-c72589b9ef3f"},
    },
    {
        "key": "palms",
        "name": "The Palms Oceanfront Club & Cabanas",
        "address_line1": "2901 Collins Avenue", "city": "Miami Beach", "state": "FL", "country": "USA", "postal_code": "33140",
        "latitude": 25.80440, "longitude": -80.12550,
        "phone": "+1 (305) 555-0177", "email": "reservations@thepalmsclub.com", "owner": "carlos",
        "description": "Mid-century modern beach club on Collins Avenue with striped cabanas, three oceanfront pools, a rooftop "
                       "cocktail lounge and an omakase seafood bar.",
        "checkin": "3:00 PM", "checkout": "11:00 AM", "timezone": "Eastern Time",
        "checkin_extra": "Early arrivals can use the oceanfront luggage lounge, showers and the beach from 9:00 AM.",
        "cancellation": [(72, 100), (24, 50)],
        "room_types": [
            {"name": "Garden Courtyard Queen", "price": 240, "guests": 2, "rooms": ["201", "202", "203", "204"], "floor_from_number": True,
             "description": "Bright queen room overlooking the tropical courtyard, a short walk from the beach."},
            {"name": "Oceanview Art Deco King", "price": 350, "guests": 2, "rooms": ["301", "302", "303", "304"], "floor_from_number": True,
             "description": "Sunlit king room in pastel coastal tones with a private balcony over the Atlantic boardwalk."},
            {"name": "Cabana Poolside Master Suite", "price": 580, "guests": 4, "rooms": ["CAB-01", "CAB-02", "CAB-03"], "floor": 1,
             "description": "Ground-floor family suite with swim-up access to the heated lagoon pool and a private cabana.",
             "amenities": ["Swim-Up Pool Access", "Private Cabana"]},
        ],
        "amenities": ["Direct Beach Access & Loungers", "Three Oceanfront Pools", "Sunset Rooftop Cocktail Lounge",
                      "Tide Omakase Seafood Bar", "Valet Parking & EV Supercharging"],
        "policies": {
            "pet_policy": "Dogs under 30 lbs are welcome in the ground-floor Cabana Poolside Master Suites for $50 per stay, with a bed and bowls provided.",
            "pool_and_spa": "The beach club and saltwater lap pool are open from 7:00 AM to 8:00 PM, when outdoor music ends. The rooftop pool is for adults only, from 9:00 AM to 7:00 PM. There is no spa on site.",
            "quiet_hours": "Quiet hours are from 11:00 PM to 7:00 AM. The rooftop lounge closes at 11:00 PM and balcony gatherings should end by then.",
            "parking_valet": "Valet parking costs $38 per night with text-to-retrieve service; Tesla Superchargers are free for guests.",
            "deposit_security": "A credit card and photo ID are required on arrival. An incidental hold of $150 per night is placed and released after departure.",
            "smoking_policy": "Rooms and pool decks are smoke-free; smoking is allowed only at the marked beach area. A $300 cleaning fee applies to any violation.",
            "breakfast_dining": "Brunch is served on the ocean terrace from 7:00 AM to 11:30 AM daily (from $24). Tide Omakase serves dinner from 6:00 PM to 10:30 PM.",
            "children_extra_beds": "Two children under 14 stay free in Cabana Poolside Master Suites. Cribs are free; beach toy kits and sunscreen are provided.",
        },
        "documents": [
            {"title": "Beach Club Guide", "category": "amenity", "access_level": "public", "text":
             "THE PALMS - BEACH CLUB GUIDE\n\n"
             "Beach service runs from 8:00 AM to 6:00 PM. Two loungers and an umbrella per room are free. Daybed cabanas cost $180 per day and include water, fruit and a dedicated server.\n\n"
             "Water sports: paddleboards ($40 per hour) and guided snorkelling trips ($85 per person) can be booked at the beach hut.\n\n"
             "The rooftop lounge opens at 4:00 PM for sunset cocktails; the rooftop pool is adults only."},
        ],
        "review_highlights": [
            "waking up to the ocean right outside our cabana was heavenly",
            "the avocado toast brunch on the ocean terrace is top tier",
            "the cabana attendants were discreet and endlessly accommodating",
            "the omakase at Tide was the best seafood of our trip",
            "sunset cocktails on the rooftop were a daily ritual",
            "it is the best private beach access in Miami without the South Beach noise",
            "the kids loved the swim-up pool from our suite",
        ],
        "review_gripes": [
            "the courtyard rooms can hear the lobby on busy nights",
            "the rooftop pool is small",
            "beach loungers go quickly after 10 AM",
        ],
        "staff": {"manager": ("Elena Rostova", "elena.rostova@thepalmsclub.com"),
                  "receptionists": [("Chris Delgado", "chris.delgado@thepalmsclub.com"), ("Aaliyah Brooks", "aaliyah.brooks@thepalmsclub.com")]},
        "media": {"hotel": ["photo-1507525428034-b723cf961d3e"],
                  "Cabana Poolside Master Suite": "photo-1520250497591-112f2f40a3f4"},
    },
    {
        "key": "tokyo",
        "name": "Tokyo Sky Haven Hotel",
        "address_line1": "2-8-1 Nishi-Shinjuku", "city": "Tokyo", "state": "Tokyo", "country": "Japan", "postal_code": "163-8001",
        "latitude": 35.68960, "longitude": 139.69210,
        "phone": "+81 3 5555 0188", "email": "omotenashi@tokyoskyhaven.jp", "owner": "kenji",
        "description": "Sky hotel on floors 40 to 52 of a Shinjuku tower, with a rooftop hinoki onsen, an Edomae sushi counter "
                       "and views of Mount Fuji and the Imperial Palace gardens.",
        "checkin": "3:00 PM", "checkout": "11:00 AM", "timezone": "Japan Standard Time",
        "checkin_extra": "Self check-in kiosks on the 40th-floor lobby work in eight languages, and staff are available 24 hours a day.",
        "cancellation": [(24, 100)],
        "room_types": [
            {"name": "Modern Zen King Room", "price": 240, "guests": 2, "rooms": ["4201", "4202", "4203", "4204", "4205"], "floor_from_number": True,
             "description": "Minimalist Japanese king room with a Simmons mattress and Shinjuku skyline views."},
            {"name": "Zen Skyline King", "price": 310, "guests": 2, "rooms": ["4401", "4402", "4403"], "floor_from_number": True,
             "description": "Corner king room with acoustic soundproofing, washi lanterns and organic linens."},
            {"name": "Fuji Panorama Sky Suite", "price": 410, "guests": 3, "rooms": ["4801", "4802"], "floor_from_number": True,
             "description": "Corner suite framing Mount Fuji, with a cedar bath and a tatami living area."},
            {"name": "Mount Fuji View Panorama Suite", "price": 680, "guests": 2, "rooms": ["5001"], "floor_from_number": True,
             "description": "Our highest suite, with floor-to-ceiling glass, a tatami tea corner and a natural cedar soaking tub.",
             "amenities": ["Cedar Soaking Tub", "Tatami Tea Corner"]},
        ],
        "amenities": ["Rooftop Hinoki Onsen", "Edomae Sushi Counter", "24-Hour Sky Fitness Gym", "1 Gbps Fibre Wi-Fi", "Sky Tea Lounge"],
        "policies": {
            "pet_policy": "Pets are not allowed in guest rooms. A partner pet hotel on the tower's ground floor offers 24-hour care with webcam access.",
            "pool_and_spa": "The rooftop hinoki onsen and infinity pool on the 52nd floor are open from 6:00 AM to 11:00 PM. Guests with tattoos are welcome and receive free cover patches.",
            "quiet_hours": "Quiet hours are from 10:00 PM to 7:00 AM.",
            "parking_valet": "Automated underground parking costs $28 per night, with 150 kW EV chargers available 24 hours.",
            "deposit_security": "A credit card and photo ID are required on arrival. An incidental hold of $100 per night is placed and released after departure.",
            "smoking_policy": "Guest rooms are smoke-free. A smoking room is available on the 40th floor. A $250 cleaning fee applies to smoking in rooms.",
            "breakfast_dining": "Japanese kaiseki and Western breakfasts are served on the 41st floor from 6:30 AM to 10:30 AM ($35). The Edomae sushi counter has two seatings, at 6:00 PM and 8:30 PM.",
            "children_extra_beds": "Children aged 12 and under stay free using existing bedding and receive child-size yukata. The Fuji Panorama Sky Suite sleeps three; no extra beds in other rooms.",
        },
        "documents": [
            {"title": "Onsen Etiquette & Timings", "category": "amenity", "access_level": "public", "text":
             "TOKYO SKY HAVEN - ROOFTOP ONSEN\n\n"
             "The hinoki-wood onsen is on the 52nd floor, overlooking Mount Fuji and Shinjuku. It is open daily from 6:00 AM to 11:00 PM.\n\n"
             "1. Shower and wash thoroughly before entering the baths.\n2. Swimsuits are not worn in the gender-separated baths.\n3. Guests with tattoos are welcome; please cover them with the free waterproof patches from the spa reception.\n4. A private family onsen can be reserved for 60 minutes for $35."},
            {"title": "Arrival Guide", "category": "faq", "access_level": "public", "text":
             "TOKYO SKY HAVEN - ARRIVAL GUIDE\n\n"
             "From Narita: the Narita Express to Shinjuku takes about 80 minutes; the airport limousine bus stops at the tower entrance.\nFrom Haneda: the limousine bus takes about 35 minutes.\n"
             "From Shinjuku Station: an 8-minute walk via the underground passage to the West Exit.\n"
             "Take the express lifts to the 40th-floor lobby. Breakfast is on the 41st floor, the tea lounge on the 51st and the onsen on the 52nd."},
        ],
        "review_highlights": [
            "the rooftop onsen at sunrise was an ethereal experience",
            "the kaiseki breakfast was fresh, authentic and beautifully plated",
            "seeing Mount Fuji on a clear morning from our suite was awe-inspiring",
            "the room was whisper-quiet despite being in Shinjuku",
            "the onsen etiquette was explained kindly and tattoo covers were provided",
            "the sushi counter was worth every yen",
            "self check-in took two minutes and the staff were wonderfully attentive",
        ],
        "review_gripes": [
            "the express lifts get busy at breakfast time",
            "the standard rooms are compact, as is usual in Tokyo",
            "the sushi counter is fully booked days ahead",
        ],
        "staff": {"manager": ("Aiko Yamamoto", "aiko.yamamoto@tokyoskyhaven.jp"),
                  "receptionists": [("Takumi Watanabe", "takumi.watanabe@tokyoskyhaven.jp"), ("Sakura Ito", "sakura.ito@tokyoskyhaven.jp")]},
        "media": {"hotel": ["photo-1540555700478-4be289fbecef", "photo-1503899036084-c55cdd92da26"],
                  "Fuji Panorama Sky Suite": "photo-1578683010236-d716f9a3f461"},
    },
    {
        "key": "ubud",
        "name": "Ubud Rainforest Villas & Zen Sanctuary",
        "address_line1": "Jalan Raya Sanggingan", "city": "Ubud", "state": "Bali", "country": "Indonesia", "postal_code": "80571",
        "latitude": -8.49460, "longitude": 115.24820,
        "phone": "+62 361 555 0192", "email": "peace@ubudzenresort.com", "owner": "wayan",
        "description": "Rainforest retreat above the Ayung River valley with private plunge-pool villas, open-air yoga pavilions, "
                       "an Ayurvedic riverside spa and farm-to-table dining.",
        "checkin": "2:00 PM", "checkout": "12:00 PM (noon)", "timezone": "Central Indonesia Time",
        "checkin_extra": "Arriving guests are welcomed with a herbal drink and a short blessing in the open-air lobby.",
        "cancellation": [(96, 100), (48, 50)],
        "room_types": [
            {"name": "Rice Terrace Suite", "price": 320, "guests": 2, "rooms": ["RT-1", "RT-2", "RT-3", "RT-4"], "floor": 1,
             "description": "Bamboo-and-stone suite with a private meditation terrace overlooking the rice fields."},
            {"name": "Ayung Riverfront Plunge Villa", "price": 560, "guests": 2, "rooms": ["AV-1", "AV-2", "AV-3"], "floor": 1,
             "description": "Open-air teak pavilion with a private volcanic-stone plunge pool and an outdoor sunken bath above the river.",
             "amenities": ["Private Plunge Pool"]},
            {"name": "Jungle Family Pool Villa", "price": 780, "guests": 4, "rooms": ["JV-1", "JV-2"], "floor": 1,
             "description": "Two-bedroom villa in the jungle canopy with a private pool, a garden and a kitchenette.",
             "amenities": ["Private Pool", "Kitchenette"]},
        ],
        "amenities": ["Private Villa Plunge Pools", "Riverside Ayurvedic Spa", "Open-Air Yoga Pavilion", "Farm-to-Table Restaurant", "Airport Transfers"],
        "policies": {
            "pet_policy": "Pets are not allowed, to protect the sanctuary's wildlife, including the resident macaques. Service animals are welcome by prior arrangement.",
            "pool_and_spa": "The riverside Ayurvedic spa is open from 9:00 AM to 9:00 PM; a 90-minute Balinese massage costs $85. Yoga classes are free at 7:00 AM and 5:00 PM in the open-air pavilion.",
            "quiet_hours": "Quiet hours are from 10:00 PM to 6:00 AM.",
            "parking_valet": "On-site parking is free. A private driver can be hired for $45 per day.",
            "deposit_security": "A credit card and photo ID are required on arrival. An incidental hold of $100 per night is placed and released after departure.",
            "smoking_policy": "Villas and suites are smoke-free; smoking is allowed only in the garden pavilion. A $200 cleaning fee applies to any violation.",
            "breakfast_dining": "A farm breakfast is included and served from 7:00 AM to 10:30 AM; a floating breakfast in your villa pool costs $35 extra. The restaurant serves dinner from 6:00 PM to 10:00 PM.",
            "children_extra_beds": "Children are welcome in Jungle Family Pool Villas, where children under 6 stay free. Babysitting costs $10 per hour. The suites and plunge villas are for two adults.",
        },
        "documents": [
            {"title": "Wellness & Yoga Programme", "category": "amenity", "access_level": "public", "text":
             "UBUD ZEN SANCTUARY - WELLNESS PROGRAMME\n\n"
             "Yoga: free hatha yoga at 7:00 AM and gentle flow at 5:00 PM daily in the open-air pavilion. Private sessions cost $40.\n\n"
             "Spa (9:00 AM to 9:00 PM): Balinese massage, 90 minutes, $85; Ayurvedic shirodhara, 60 minutes, $95; flower bath ritual for two, $120.\n\n"
             "Experiences: a water blessing at a temple ($60 per person) and a sunrise trek on Mount Batur ($95 per person) can be booked at reception."},
            {"title": "Arrival & Transfers", "category": "faq", "access_level": "public", "text":
             "UBUD ZEN SANCTUARY - ARRIVAL\n\n"
             "The drive from Bali's Ngurah Rai airport takes 75 to 90 minutes. Our private transfer costs $40 one way per car (up to 3 guests with luggage). Book 24 hours ahead with your flight number.\n\n"
             "Ubud centre is 10 minutes away by our free shuttle, which leaves every hour from 9:00 AM to 9:00 PM."},
        ],
        "review_highlights": [
            "our plunge pool hovered right over the rainforest canopy",
            "morning yoga to the sound of the Ayung River was transcendent",
            "the Ayurvedic treatment completely rejuvenated me",
            "the farm-to-table dinners under the stars were delicious",
            "the floating breakfast in our villa pool was worth every penny",
            "the staff welcomed us with a blessing that set the tone for the stay",
            "the free shuttle to Ubud centre was very convenient",
        ],
        "review_gripes": [
            "the monkeys are cheeky, so keep doors closed",
            "the path to the riverfront villas is steep",
            "the drive from the airport is long",
        ],
        "staff": {"manager": ("Made Wirawan", "made.wirawan@ubudzenresort.com"),
                  "receptionists": [("Putu Ayu", "putu.ayu@ubudzenresort.com"), ("Komang Sari", "komang.sari@ubudzenresort.com")]},
        "media": {"hotel": ["photo-1537996194471-e657df975ab4"]},
    },
]

REVIEW_OPENERS = {
    5: ["An absolute dream of a stay", "Faultless from start to finish", "We are already planning to come back", "Exceeded every expectation",
        "One of the best hotels we have stayed in", "Pure luxury"],
    4: ["A lovely stay overall", "Very good, with a couple of small niggles", "Great hotel and friendly team", "We really enjoyed it",
        "Beautiful property"],
    3: ["A decent stay, but not quite what we hoped", "Good location, mixed experience", "Some highs and some lows"],
}
