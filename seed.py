"""Seed script for ClickBook.

Emits templates whose `sections_config` matches the frontend `SectionDef` shape
(frontend/src/data/sections.ts): { id, type, name, visible, data, style }. This shape is
what `SectionRenderer` consumes, so the editor can load, edit, and publish
templates without schema transforms.

Re-running this script refreshes the 12+ templates in place (keeps existing
users and their sites).
"""
from copy import deepcopy
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import Template, User
from app.utils.helpers import slugify

app = create_app()

DEFAULT_STYLE = {"paddingY": 80, "align": "center", "width": "boxed", "radius": 16}


def section(type_, name, data, style=None, visible=True, id_=None):
    return {
        "id": id_ or f"s_{slugify(name)}_{type_}",
        "type": type_,
        "name": name,
        "visible": visible,
        "data": data,
        "style": {**DEFAULT_STYLE, **(style or {})},
    }


# ---------- Section factories ----------

def hero(headline, subheadline, eyebrow="", cta_primary="Get started", cta_secondary="Learn more", bg=""):
    return section("hero", "Hero", {
        "eyebrow": eyebrow,
        "headline": headline,
        "subheadline": subheadline,
        "ctaPrimary": cta_primary,
        "ctaPrimaryUrl": "#",
        "ctaSecondary": cta_secondary,
        "ctaSecondaryUrl": "#",
        "bgImage": bg,
    })


def about(title, body, image=""):
    return section("about", "About", {"title": title, "body": body, "image": image}, {"align": "left"})


def features(title, subtitle, items, columns=3):
    return section("features", "Features", {
        "title": title, "subtitle": subtitle, "columns": columns, "items": items,
    })


def testimonials(title, items):
    return section("testimonials", "Testimonials", {"title": title, "items": items})


def pricing(title, subtitle, plans):
    return section("pricing", "Pricing", {"title": title, "subtitle": subtitle, "plans": plans})


def team(title, members):
    return section("team", "Team", {"title": title, "members": members})


def gallery(title, images, columns=3):
    return section("gallery", "Gallery", {"title": title, "columns": columns, "images": images})


def cta(title, body, cta_text="Get started"):
    return section("cta", "Call to action", {"title": title, "body": body, "cta": cta_text, "ctaUrl": "#"})


def contact(title, email, show_form=True):
    return section("contact", "Contact", {"title": title, "email": email, "showForm": show_form})


def footer(brand, copyright_):
    return section("footer", "Footer", {
        "brand": brand, "copyright": copyright_, "links": ["Privacy", "Terms", "Contact"],
    })


# ---------- Reusable feature item presets ----------
def feat(title, body, icon="Check"):
    return {"title": title, "body": body, "icon": icon}


def plan(name, price, period, feats, highlight=False, cta_label=None):
    return {
        "name": name, "price": price, "period": period,
        "features": feats, "highlight": highlight,
        "cta": cta_label or f"Choose {name}",
    }


def review(name, role, quote, rating=5):
    return {"name": name, "role": role, "quote": quote, "rating": rating}


def member(name, role, image=""):
    return {"name": name, "role": role, "image": image}


# ---------- Template section-sets ----------

def gym_sections():
    return [
        hero(
            "Train Harder. Live Better.",
            "Expert coaching, premium equipment, and a motivating community.",
            eyebrow="24/7 Access",
            cta_primary="Start Free Trial", cta_secondary="View Classes",
            bg="https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=1600",
        ),
        features("Why IronPulse", "Everything you need to crush your goals", [
            feat("24/7 Access", "Work out on your schedule.", "Zap"),
            feat("Expert Coaches", "Certified trainers at every level.", "Heart"),
            feat("Recovery Zone", "Sauna, massage, stretch area.", "Sparkles"),
            feat("Nutrition Plans", "Custom plans from our dietitians.", "Check"),
            feat("Mobile App", "Track PRs and book classes.", "Globe"),
            feat("Clean & Safe", "Spotless facilities, 24/7.", "Shield"),
        ], columns=3),
        team("Meet the coaches", [
            member("Alex Cruz", "Strength Coach"),
            member("Maya Lee", "Yoga Instructor"),
            member("Derek Shaw", "HIIT Coach"),
        ]),
        pricing("Membership plans", "Flexible, cancel anytime", [
            plan("Starter", "$29", "/mo", ["Gym floor", "Locker", "App access"]),
            plan("Pro", "$59", "/mo", ["All classes", "Sauna", "Nutrition"], highlight=True),
            plan("Elite", "$99", "/mo", ["PT sessions", "Meal plan", "Priority"]),
        ]),
        testimonials("Member stories", [
            review("Sara P.", "Member", "Best gym experience ever."),
            review("Michael T.", "Member", "Lost 20 pounds in 3 months!"),
        ]),
        cta("Ready to start?", "Book a free tour today.", "Book a tour"),
        contact("Get in touch", "hello@ironpulse.com"),
        footer("IronPulse Gym", "© 2026 IronPulse Gym. All rights reserved."),
    ]


def spa_sections():
    return [
        hero(
            "Relax. Rejuvenate. Renew.",
            "Luxury spa treatments in a serene sanctuary.",
            eyebrow="Award-winning spa",
            cta_primary="Book a treatment", cta_secondary="View menu",
            bg="https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=1600",
        ),
        about("A sanctuary for your senses",
              "Our therapists combine ancient techniques with modern wellness science to help you unwind, reset, and glow.",
              "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=900"),
        features("Treatments", "Curated experiences for body & mind", [
            feat("Deep Tissue Massage", "Release muscle tension.", "Heart"),
            feat("Aromatherapy", "Essential oils for calm.", "Sparkles"),
            feat("Facial Rituals", "Glowing, hydrated skin.", "Star"),
            feat("Body Scrubs", "Renew from head to toe.", "Check"),
        ], columns=4),
        pricing("Packages", "Treat yourself or someone you love", [
            plan("Hour of Calm", "$89", "/session", ["60-min massage", "Tea service"]),
            plan("Glow Ritual", "$189", "/session", ["Facial", "Massage", "Scrub"], highlight=True),
            plan("Day Retreat", "$349", "/day", ["Full spa day", "Lunch", "Robe"]),
        ]),
        testimonials("Guest reviews", [
            review("Jenna R.", "Guest", "I left feeling like a new person."),
            review("Omar S.", "Guest", "The most relaxing place in the city."),
        ]),
        contact("Book your visit", "bookings@zenleaf.com"),
        footer("ZenLeaf Spa", "© 2026 ZenLeaf Spa. All rights reserved."),
    ]


def realty_sections():
    return [
        hero(
            "Find Your Dream Home",
            "Curated listings and expert agents in every neighborhood.",
            eyebrow="Trusted by 10,000+ families",
            cta_primary="Browse homes", cta_secondary="Meet agents",
            bg="https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=1600",
        ),
        features("Why PrimeNest", "Data-driven matchmaking for buyers & sellers", [
            feat("AI Matching", "Listings tailored to you.", "Sparkles"),
            feat("Expert Agents", "Local specialists in every area.", "Shield"),
            feat("Virtual Tours", "Explore before you visit.", "Globe"),
        ]),
        gallery("Featured properties", [
            "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800",
            "https://images.unsplash.com/photo-1613977257363-707ba9348227?w=800",
            "https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=800",
            "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=800",
            "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=800",
            "https://images.unsplash.com/photo-1600585154526-990dced4db0d?w=800",
        ]),
        testimonials("Client stories", [
            review("The Martinez Family", "Homeowners", "Closed in 30 days — couldn't be happier."),
            review("Priya K.", "First-time buyer", "They made it feel so easy."),
        ]),
        cta("Ready to move?", "Schedule a free consultation today.", "Get started"),
        contact("Talk to an agent", "hello@primenest.com"),
        footer("PrimeNest Realty", "© 2026 PrimeNest Realty. All rights reserved."),
    ]


def restaurant_sections():
    return [
        hero(
            "Farm-to-Table Dining",
            "Seasonal menus from our open-fire kitchen.",
            eyebrow="Est. 2017",
            cta_primary="Reserve a table", cta_secondary="View menu",
            bg="https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=1600",
        ),
        about("Rooted in the seasons",
              "Every plate starts with local farmers. Our menu shifts with the harvest and the fire never goes out.",
              "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=900"),
        gallery("From our kitchen", [
            "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=800",
            "https://images.unsplash.com/photo-1567620905732-2d1ec7ab7445?w=800",
            "https://images.unsplash.com/photo-1540189549336-e6e99c3679fe?w=800",
            "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=800",
            "https://images.unsplash.com/photo-1551218808-94e220e084d2?w=800",
            "https://images.unsplash.com/photo-1476224203421-9ac39bcb3327?w=800",
        ]),
        testimonials("Reviews", [
            review("James B.", "Food critic", "The best tasting menu in town."),
            review("Elena D.", "Regular", "I dream about the short ribs."),
        ]),
        cta("Hungry yet?", "Tables fill up fast — book ahead.", "Reserve now"),
        contact("Visit us", "hello@forkandflame.com"),
        footer("Fork & Flame", "© 2026 Fork & Flame."),
    ]


def portfolio_sections():
    return [
        hero(
            "Designs that tell stories",
            "Brand, product, and digital design for ambitious teams.",
            eyebrow="Portfolio 2026",
            cta_primary="View work", cta_secondary="Get in touch",
            bg="https://images.unsplash.com/photo-1558655146-9f40138edfeb?w=1600",
        ),
        about("Hi, I'm Astra.",
              "I help founders turn fuzzy ideas into shipping products. 10+ years of design across SaaS, fintech, and consumer.",
              "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=900"),
        gallery("Selected work", [
            "https://images.unsplash.com/photo-1559028012-481c04fa702d?w=800",
            "https://images.unsplash.com/photo-1581291518633-83b4ebd1d83e?w=800",
            "https://images.unsplash.com/photo-1561070791-2526d30994b8?w=800",
            "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800",
            "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?w=800",
            "https://images.unsplash.com/photo-1586717791821-3f44a563fa4c?w=800",
        ], columns=3),
        testimonials("Kind words", [
            review("Nadia F.", "Founder, Luma", "Delivered above expectations, on time."),
            review("Tom R.", "PM, Orbit", "The best designer we've worked with."),
        ]),
        cta("Have a project in mind?", "Let's make something great together.", "Start a project"),
        contact("Say hello", "astra@design.studio"),
        footer("Astra Studio", "© 2026 Astra Studio."),
    ]


def agency_sections():
    return [
        hero(
            "Scale your brand",
            "Full-service growth marketing for ambitious startups.",
            eyebrow="Nova Agency",
            cta_primary="Book a strategy call", cta_secondary="See case studies",
            bg="https://images.unsplash.com/photo-1552664730-d307ca884978?w=1600",
        ),
        features("What we do", "End-to-end growth services", [
            feat("Performance Ads", "Paid acquisition that converts.", "Zap"),
            feat("Brand Strategy", "Positioning that stands out.", "Sparkles"),
            feat("Content & SEO", "Traffic that compounds.", "Globe"),
            feat("Conversion", "Funnels tuned for revenue.", "Rocket"),
        ], columns=2),
        team("The team", [
            member("Lena Ortiz", "Founder & Strategist"),
            member("Rafi Kaur", "Head of Paid"),
            member("Noah Webb", "Creative Director"),
        ]),
        testimonials("Client wins", [
            review("Casey L.", "CEO, BrightBox", "Tripled our MRR in 6 months."),
            review("Dana P.", "Head of Growth, Wave", "Clearest strategy we've ever had."),
        ]),
        cta("Let's grow together", "Book a free 30-min strategy call.", "Book a call"),
        contact("Talk to Nova", "hello@novaagency.com"),
        footer("Nova Agency", "© 2026 Nova Agency."),
    ]


def medical_sections():
    return [
        hero(
            "Modern care, human touch",
            "A family clinic for every stage of life.",
            eyebrow="Accepting new patients",
            cta_primary="Book an appointment", cta_secondary="Our services",
            bg="https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=1600",
        ),
        features("Services", "Primary, preventive, and specialty care", [
            feat("Primary Care", "Annual exams & wellness.", "Heart"),
            feat("Pediatrics", "Care for little ones.", "Sparkles"),
            feat("Dermatology", "Skin health specialists.", "Shield"),
            feat("Telehealth", "Visit from home.", "Globe"),
        ], columns=4),
        team("Meet our physicians", [
            member("Dr. Priya Shah", "Family Medicine"),
            member("Dr. Ben Cohen", "Pediatrics"),
            member("Dr. Ayo Adeyemi", "Dermatology"),
        ]),
        testimonials("Patient reviews", [
            review("Rebecca H.", "Patient", "The warmest clinic I've been to."),
            review("Tomás G.", "Patient", "Dr. Shah changed our family's health."),
        ]),
        contact("Book a visit", "care@brightclinic.com"),
        footer("BrightCare Clinic", "© 2026 BrightCare Clinic."),
    ]


def education_sections():
    return [
        hero(
            "Learn anything, on your schedule",
            "Live classes and on-demand courses from world-class instructors.",
            eyebrow="Now enrolling",
            cta_primary="Browse courses", cta_secondary="For teams",
            bg="https://images.unsplash.com/photo-1513258496099-48168024aec0?w=1600",
        ),
        features("Why Lumina", "Learning that actually sticks", [
            feat("Live cohorts", "Learn with peers, not alone.", "Sparkles"),
            feat("Expert instructors", "Practitioners, not lecturers.", "Star"),
            feat("Career outcomes", "Job-ready skills.", "Rocket"),
        ]),
        pricing("Plans", "For individuals and teams", [
            plan("Student", "$19", "/mo", ["All on-demand courses", "Community"]),
            plan("Pro", "$49", "/mo", ["Live cohorts", "Mentorship", "Certificates"], highlight=True),
            plan("Team", "$199", "/mo", ["5 seats", "Admin dashboard", "SSO"]),
        ]),
        testimonials("Learner stories", [
            review("Ines M.", "Data analyst", "Landed my first data job in 4 months."),
            review("Kiran J.", "Product manager", "The live cohorts are incredible."),
        ]),
        cta("Start learning today", "7-day free trial on every plan.", "Start free trial"),
        contact("Questions?", "hello@lumina.school"),
        footer("Lumina School", "© 2026 Lumina School."),
    ]


def ecommerce_sections():
    return [
        hero(
            "Essentials, redefined",
            "Elevated basics made from responsibly sourced materials.",
            eyebrow="New season",
            cta_primary="Shop now", cta_secondary="Our story",
            bg="https://images.unsplash.com/photo-1483985988355-763728e1935b?w=1600",
        ),
        gallery("Featured products", [
            "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=800",
            "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=800",
            "https://images.unsplash.com/photo-1556906781-9a412961c28c?w=800",
            "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800",
            "https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=800",
            "https://images.unsplash.com/photo-1542272604-787c3835535d?w=800",
        ], columns=3),
        features("Why Rume", "More than just clothes", [
            feat("Responsibly made", "Organic & recycled fabrics.", "Heart"),
            feat("Free shipping", "On orders over $75.", "Globe"),
            feat("Easy returns", "60-day no-questions.", "Check"),
        ], columns=3),
        testimonials("Customer love", [
            review("Laila O.", "Customer", "Softest tees I've ever owned."),
            review("Mark D.", "Customer", "Fit is perfect, every time."),
        ]),
        cta("Join the club", "Get 15% off your first order.", "Sign up"),
        footer("Rume Apparel", "© 2026 Rume Apparel."),
    ]


def business_sections():
    return [
        hero(
            "Run your business, effortlessly",
            "All-in-one software for modern small businesses.",
            eyebrow="Built for teams of 5–50",
            cta_primary="Start free trial", cta_secondary="Watch demo",
            bg="https://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=1600",
        ),
        features("Everything in one place", "Invoicing, CRM, scheduling — done.", [
            feat("Invoicing", "Get paid faster.", "Zap"),
            feat("CRM", "Track every deal.", "Sparkles"),
            feat("Scheduling", "Book clients online.", "Globe"),
            feat("Reporting", "Know your numbers.", "Shield"),
        ], columns=4),
        pricing("Simple pricing", "Start free, upgrade when ready", [
            plan("Starter", "Free", "", ["Up to 3 users", "Core features"]),
            plan("Growth", "$49", "/mo", ["Unlimited users", "Integrations"], highlight=True),
            plan("Scale", "$149", "/mo", ["Priority support", "Advanced reports"]),
        ]),
        testimonials("Teams love Brightfield", [
            review("Yuki T.", "Owner, Petalworks", "Cut our admin time in half."),
            review("Amir R.", "CEO, Boxly", "Replaced 4 other tools."),
        ]),
        cta("Try it free", "No credit card required.", "Start free trial"),
        footer("Brightfield", "© 2026 Brightfield Software."),
    ]


def freelancer_sections():
    return [
        hero(
            "Independent work, beautifully run",
            "The operating system for freelancers and consultants.",
            eyebrow="Solo-friendly",
            cta_primary="Get started free",
            cta_secondary="See features",
            bg="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=1600",
        ),
        about("Built by freelancers, for freelancers",
              "Proposals, contracts, invoices, and time tracking — all in one place.",
              "https://images.unsplash.com/photo-1556740772-1a741367b93e?w=900"),
        features("Key features", "Focus on work, not admin", [
            feat("Proposals", "Win more clients.", "Rocket"),
            feat("Contracts", "Legally solid templates.", "Shield"),
            feat("Invoicing", "Automated reminders.", "Zap"),
        ]),
        testimonials("Freelancers love us", [
            review("Nora A.", "Designer", "I get paid 2 weeks faster now."),
            review("Ivan P.", "Developer", "The proposal builder is 🔥."),
        ]),
        cta("Ready to level up?", "Free forever, upgrade anytime.", "Sign up free"),
        footer("SoloDeck", "© 2026 SoloDeck."),
    ]


def saas_sections():
    return [
        hero(
            "Ship faster, sleep better",
            "The monitoring platform your team actually enjoys using.",
            eyebrow="Trusted by 2,500+ teams",
            cta_primary="Start free", cta_secondary="Read docs",
            bg="https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1600",
        ),
        features("Why Pulsar", "Observability without the headache", [
            feat("Smart alerts", "Signal, not noise.", "Zap"),
            feat("Tracing", "End-to-end visibility.", "Globe"),
            feat("Dashboards", "Beautiful by default.", "Sparkles"),
            feat("Integrations", "100+ out of the box.", "Check"),
        ], columns=4),
        pricing("Pricing", "Per-seat, no gotchas", [
            plan("Hobby", "Free", "", ["1 project", "Community"]),
            plan("Team", "$29", "/user/mo", ["Unlimited projects", "Priority alerts"], highlight=True),
            plan("Business", "$79", "/user/mo", ["SSO", "Audit logs", "SLAs"]),
        ]),
        testimonials("Engineering teams love Pulsar", [
            review("Chen W.", "SRE Lead", "Cut our MTTR by 60%."),
            review("Aisha O.", "CTO", "Our on-call sleeps again."),
        ]),
        cta("Start monitoring in 5 minutes", "Free tier forever.", "Start free"),
        footer("Pulsar", "© 2026 Pulsar Inc."),
    ]


def event_sections():
    return [
        hero(
            "The summit of the year",
            "Three days. 60 speakers. One unforgettable experience.",
            eyebrow="Oct 14–16, 2026 · San Francisco",
            cta_primary="Get tickets", cta_secondary="View speakers",
            bg="https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=1600",
        ),
        features("What to expect", "Curated content, real connections", [
            feat("Keynotes", "Industry-defining talks.", "Star"),
            feat("Workshops", "Hands-on learning.", "Sparkles"),
            feat("Networking", "Meet your next co-founder.", "Heart"),
        ]),
        team("Featured speakers", [
            member("Dr. Ada Wen", "AI Researcher"),
            member("Miguel Soto", "Founder, Helio"),
            member("Rin Takeda", "VP Product, Kori"),
        ]),
        pricing("Tickets", "Early-bird pricing ends Aug 1", [
            plan("Standard", "$399", "", ["All talks", "Lunch", "Swag"]),
            plan("VIP", "$899", "", ["Front row", "Speaker dinner", "Workshops"], highlight=True),
            plan("Team of 5", "$1,699", "", ["5 standard passes", "Reserved table"]),
        ]),
        cta("Don't miss it", "Early-bird pricing ends soon.", "Get tickets"),
        contact("Questions?", "info@summit26.com"),
        footer("Summit 26", "© 2026 Summit Events."),
    ]


# ---------- Template catalogue ----------

TEMPLATES = [
    {"name": "IronPulse Gym", "category": "gym", "description": "Powerful gym & fitness template with pricing and classes.", "thumbnail": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=800", "featured": True, "sections": gym_sections},
    {"name": "ZenLeaf Spa", "category": "spa", "description": "Calm, luxurious spa site with treatment packages.", "thumbnail": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=800", "featured": False, "sections": spa_sections},
    {"name": "PrimeNest Realty", "category": "real_estate", "description": "High-converting real estate site with listings gallery.", "thumbnail": "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800", "featured": False, "sections": realty_sections},
    {"name": "Fork & Flame", "category": "restaurant", "description": "Elegant restaurant site with menu gallery.", "thumbnail": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800", "featured": True, "sections": restaurant_sections},
    {"name": "Astra Portfolio", "category": "portfolio", "description": "Creative designer portfolio with case study gallery.", "thumbnail": "https://images.unsplash.com/photo-1558655146-9f40138edfeb?w=800", "featured": False, "sections": portfolio_sections},
    {"name": "Nova Agency", "category": "agency", "description": "Growth agency site with team and case studies.", "thumbnail": "https://images.unsplash.com/photo-1552664730-d307ca884978?w=800", "featured": False, "sections": agency_sections},
    {"name": "BrightCare Clinic", "category": "medical", "description": "Modern medical clinic with services and doctors.", "thumbnail": "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=800", "featured": False, "sections": medical_sections},
    {"name": "Lumina School", "category": "education", "description": "Online school with courses, plans, and testimonials.", "thumbnail": "https://images.unsplash.com/photo-1513258496099-48168024aec0?w=800", "featured": True, "sections": education_sections},
    {"name": "Rume Apparel", "category": "ecommerce", "description": "Ecommerce template for apparel and lifestyle brands.", "thumbnail": "https://images.unsplash.com/photo-1483985988355-763728e1935b?w=800", "featured": False, "sections": ecommerce_sections},
    {"name": "Brightfield Business", "category": "business", "description": "All-in-one SMB software landing page.", "thumbnail": "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=800", "featured": False, "sections": business_sections},
    {"name": "SoloDeck Freelancer", "category": "business", "description": "Freelancer operating system landing page.", "thumbnail": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800", "featured": False, "sections": freelancer_sections},
    {"name": "Pulsar SaaS", "category": "business", "description": "B2B SaaS product page with pricing tiers.", "thumbnail": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800", "featured": True, "sections": saas_sections},
    {"name": "Summit 26 Event", "category": "business", "description": "Conference / event landing page with tickets & speakers.", "thumbnail": "https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800", "featured": False, "sections": event_sections},
]


def seed():
    with app.app_context():
        db.create_all()

        # Users (create if missing)
        if not User.query.filter_by(email="admin@clickbook.com").first():
            db.session.add(User(
                name="ClickBook Admin",
                email="admin@clickbook.com",
                password_hash=generate_password_hash("Admin@123"),
                role="admin",
                plan="business",
            ))
        for name, email, plan in [
            ("Jane Builder", "jane@clickbook.com", "starter"),
            ("Mark Creator", "mark@clickbook.com", "pro"),
        ]:
            if not User.query.filter_by(email=email).first():
                db.session.add(User(
                    name=name, email=email,
                    password_hash=generate_password_hash("User@12345"),
                    plan=plan,
                ))

        # Templates: upsert — refresh sections_config every run so the seed
        # always matches the current frontend SectionDef shape.
        for t in TEMPLATES:
            slug = slugify(t["name"])
            existing = Template.query.filter_by(slug=slug).first()
            payload = dict(
                name=t["name"],
                slug=slug,
                category=t["category"],
                description=t["description"],
                thumbnail_url=t["thumbnail"],
                preview_url=t["thumbnail"],
                sections_config=deepcopy(t["sections"]()),
                global_styles={
                    "fonts": ["Inter", "Poppins"],
                    "colors": {"primary": "#2563eb", "background": "#ffffff", "text": "#111827"},
                    "spacing": {"section_y": "80px"},
                },
                is_featured=t["featured"],
                is_active=True,
            )
            if existing:
                for k, v in payload.items():
                    setattr(existing, k, v)
            else:
                db.session.add(Template(**payload))

        db.session.commit()
        print(f"Seed complete — {len(TEMPLATES)} templates ready.")


if __name__ == "__main__":
    seed()