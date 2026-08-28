"""
Carica liste di brand come collezioni di aziende nel profilo.

    python scripts/seed_collections.py            # carica
    python scripts/seed_collections.py --dry-run  # mostra cosa farebbe

Idempotente: rilanciarlo non crea doppioni. Le collezioni si riconoscono
per nome, i membri per nome (case-insensitive) dentro la collezione.

Nota su cosa NON fa: non verifica che i brand esistano né che assumano.
È una lista di desideri, non un registro — la verifica avviene dopo, quando
una collezione viene applicata a una ricerca e il sistema cerca l'ATS di
ogni azienda.
"""
import argparse
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app import models  # noqa: E402

# ---------------------------------------------------------------------
# I dati. Una voce per riga logica, separate da virgola come fornite.
# ---------------------------------------------------------------------
COLLECTIONS: list[tuple[str, str, str]] = [
    (
        "Beauty e profumeria",
        "Profumi, cosmetici, skincare, haircare",
        """A4 COSMETICS, Abercrombie & Fitch, Accendis, Acqua Alpes, Acqua di Genova,
Acqua di Parma, African Wonder, Ahava, Aigner, Alessandro, Alexandre.J, American Crew,
Anastasia Beverly Hills, Anfas, Annayake, Anne Möller, ANNY, Anua, APRICOT, Aramis,
Arcaya, Ardell, Ariana Grande, Armani, Artemis, ASABI, Attar Collection, Augustinus Bader,
Australian Bodycare, Aveda, Axis-Y, Ayer, Azzaro, BABOR, BaBylissPRO, Baldessarini,
Baobab, Barberino's, bareMinerals, Beauté Pacifique, Beauty of Joseon, beautyblender,
Belif, Bellápierre Cosmetics, Bellody, Benamôr, Better World Fragrance House by Drake,
Bettina Barty, Betty Barclay, Billie Eilish, BioEffect, BIOSILK, Biotherm, Biotherm Homme,
Biotulin, Bobbi Brown, Boellis 1924, BondiBoost, BPERFECT, Bridgerton, Brow Code,
Bruno Banani, BULLFROG, Bumble and bumble, Burberry, Bvlgari, By Terry, Cacharel,
Calvin Klein, Captain's Essentials, Carolina Herrera, Cartier, Catrice, Cerruti,
Charlotte Meentzen, Chanel, Chloé, Chopard, Christina Aguilera, CLEAN Reserve, Clinique,
Cloud Nine, Clubman Pinaud, COCUNAT, Collistar, COLOR WOW, Colour Freedom, Comodynes,
Cosmos, COSRX, Courrèges, Cristiano Ronaldo, Curaprox, Curlsmith, Da Vinci, Davidoff,
DEAR DAHLIA, Declaré, Diesel, DKNY, Doctor Eckstein, Dr. Bronner's, Dr. K Soap Company,
Dr. Susanne von Schmiedeberg, Drybar, Dsquared2, Dior, Ebenholz skincare,
Efalock Professional, Eino, Eisenberg, EL GANSO, Elie Saab, Elizabeth Arden, Engelsrufer,
ERBE, Erborian, Erno Laszlo, Escada, Essence, Estée Lauder, Etro, Evody, Fable & Mane,
Fanola, FAQ Swiss, Farmacy Beauty, Fekkai, feschi, Filorga, florence by mills, Flormar,
Foreo, Fudge, G9 Skin, Gabriela Sabatini, Gainsboro, GAMMA+, GANT, Geek & Gorgeous,
Giardino Benessere, Gisada, GIVENCHY, Glamfume, GLOV, Gold Professional, Goldwell, Gritti,
Grown Alchemist, Gucci, GUERLAIN, Guy Laroche, HAIR RITUEL by SISLEY, Halloween, Headspace,
Hej Organic, Helena Rubinstein, Helene Fischer, Hemcael, Hercules Sägemann, Herôme,
HH Simonsen, Hildegard Braukmann, Histoires de Parfums, Hollister, Hugo Boss,
HYPOAllergenic, I Want You Naked, INDOLA, Inglot, INITIO Parfums Privés, Innersense,
IRÄYE, Isabey Paris, Isadora, Issey Miyake, it Cosmetics, J.F. Schwarzlose Berlin, Jaguar,
Jardin Bohème, Jardin de France, Jean Paul Gaultier, Jean-Charles Brosseau, Jesus del Pozo,
Jette Joop, Jil Sander, Jimmy Choo, Jo Malone London, John Player Special, JOOP!, Jovan,
Juicy Couture, Juvena, Karl Lagerfeld, Kativa, KENZO, Kerasilk, Kérastase, Khloé Kardashian,
Kiehl's, King Brown, KISS, Klairs, KLAPP, KMS, Kneipp, Knize, KORA Organics, Korres,
Kylie Jenner Cosmetics, Kylie Skin, L'Oréal Professionnel Paris, La Bruket, La Mer, Lacoste,
LAJA, Lalique, Lancaster, Lancôme, Lanolips, Lanvin, Laura Biagiotti,
Lavandière de Provence, Lavera, Le Couvent Maison de Parfum, LENGLING MUNICH,
LIGNE ST BARTH, Linari, Liquides Imaginaires, Living Proof, LOLAVIE, Londa Professional,
Lord & Berry, Lovehoney mon ami, Lumene, Lunar Glow, Luvia Cosmetics, M-Up´s, M2 BEAUTÉ,
MÁDARA, Maison Margiela, Maison Matine, Maison Tahité, Manic Panic, Marbert, Marc Jacobs,
Margaret Dabbs, Maria Nila, Mario Badescu, Marlies Möller, Masakï Matsushïma,
MBR Medical Beauty Research, MCM, Mercedes Benz Perfume, Mermade Hair, MERME Berlin,
Michael Kors, Michael Michalsky, Micro Cell, Milk Touch, MINICO, minLen, Miro, Miss Sophie,
MISSHA, Miu Miu, Mixsoon, MIZENSIR, Molinard, Montblanc, Morphe, Moschino, MUGLER,
my olivanna, Mystikum, Nailberry, Naomi Campbell, Narciso Rodriguez, Natucain,
NEST NEW YORK, Nesti Dante Firenze, Neuma, Neutrea 5% Urea, NEW LAYER, NIANCE, Nina Ricci,
Nioxin, NISHANE, Nobile 1942, NORDIK, Nuxe, Oceanwell, Olaplex, Olivia Garden,
Olivia Garden Club, One.two.free!, OPI, Orebella, Original & Mineral, Oster, Otto Kern,
Palina, Pana Dora Sweden, parfumdreams, parfumdreamsKIDS, Parfums d'Elmar,
Parfums de Marly, Parlux, Payot, Pedi Couture, Pestle & Mortar, Peter Thomas Roth, PHYTO,
Physicians Formula, Picasso, Pig & Hen, Pixi, pmd., PoBeau, Porsche Design, Prada,
Primavera, Proraso, puremetics, Rabanne, Ralph Lauren, Ramón Monegal, Rancé,
Real Techniques, Redken, Regincós, René Furterer, Reuzel, Revamp Professional, RevitaSun,
Revlon, Revlon Professional, Revolution Skincare, Rexaline, Roberto Cavalli,
Roberto Ugolini, Rochas, ROMP, Rosense, Rosental Organics, Round Lab, s.Oliver, Sans Soucis,
Santaverde, Sante Naturkosmetik, Sassoon, SBT cell identical care, Scandinavian Biolabs,
Schwarzkopf Professional, Sebastian, SENSAI, Serge Lutens, Shiseido, Shu Uemura, SHYNE,
Simone Andreoli, Sir Irisch Moos, SISLEY, Skin1004, skin689, Slick Gorilla, slip,
Soap & Glory, sober, Sol de Janeiro, Sparitual, St.Tropez, StarSkin, Stylecraft, Sun Matters,
Suntique, Swiss Smile, Swissdent, System Professional Lipid Code, T-LAB Professional, T3,
Tabac, Tana, Tangle Teezer, Tautropfen, Teaology, TERMIX, THAMEEN London, The Balm,
THE FOX TAN, The Handmade Soap, The INKEY List, THE MERCHANT OF VENICE,
The Organic Pharmacy, This Works, Tiffany & Co., TIGI, Tiziana Terenzi, Tom Ford,
Tommy Hilfiger, Toni Gard, Torriden, Tree Hut, Trussardi, TYPEBEA, Umberto Giannini,
UNbrush, Unleashia, Uppercut Deluxe, Urtekram, V Canto, Valentino, VALJUES, VARIS, Versace,
Viktor & Rolf, Village, We Love The Planet, We-Vibe, WELEDA, Wella, Wet Brush, wet n wild,
WHAMISA, Widian, Womanizer, WOMO, Woods Copenhagen, WoodWick, XERJOFF,
XERJOFF Casamorati, Yves Saint Laurent, Yu Beauty, Zadig & Voltaire, Zao, Zarkoperfume,
ZEW for men, 3LAB, 4711, 4711 Acqua Colonia, Byredo, Creed, Amouage,
Maison Francis Kurkdjian, Diptyque, Penhaligon's, L'Artisan Parfumeur, Parfums de Nicolaï,
Floris London, Clive Christian, Roja Parfums, Comme des Garçons, Miller Harris, Orto Parisi,
Nasomatto, Boadicea the Victorious, Memo Paris, Juliette Has a Gun, The Different Company,
Atelier Cologne, Etat Libre d'Orange""",
    ),
    (
        "Orologi",
        "Orologeria, dal lusso allo smartwatch",
        """A. Lange & Söhne, AB AETERNO, Accutron, Alpina, Angelus, Apple Watch, Aquastar,
Arnold & Son, Audemars Piguet, AVI-8, Baltic, Baume & Mercier, Bell & Ross, Blancpain,
Bonvier, Breguet, Breil, Breitling, Brellum, Bremont, Bulgari, Bulova, Calamai,
Calvin Klein, Cartier, Casio, Certina, Chopard, Citizen, Cluse, Code41, Cyrus, Czapek,
D1 Milano, Daniel Wellington, Delbana, Doxa, Eberhard, echo-neutra, Edox, Emporio Armani,
Fathers Watches, Festina, Fonderia Lab, Formex, Fossil, Frederique Constant, Garmin,
Gigandet, Girard Perregaux, Glashütte Original, Glycine, Grand Seiko, Green Time,
Greubel Forsey, H. Moser & Cie, Hamilton, Hautlence, Henry London, Hera Watches, Huawei,
Hublot, Ichnos, Invicta, ITA Time, IWC, Jacob & Co, Jaeger LeCoultre, Jaquet Droz, Kronaby,
Larsen & Eriksen, Locman, Longines, Lorenz, Louis Erard, Louis Vuitton, Maurice Lacroix,
MB&F, Meccaniche Veneziane, Michael Kors, Mido, Minerva, Monta, Naga, Nautica, Nima,
Nivada, Nixon, Nomos Glashütte, Norqain, Officine Tecniche, Ollech & Wajs, Omega, Orient,
Oris, Out of Order Watches, Panerai, Parmigiani Fleurier, Patek Philippe, Perrelet, Perseo,
Philip Watch, Piaget, Porsche Design, Rado, Ressence, Richard Mille, Rifle, Rolex, Rotary,
Samsung, Scuro Watch, Seagull, Sector, Seiko, Sinn, Spinnaker, Squale, Stuhrling, Suunto,
Swatch, Swiss Eagle, Tag Heuer, Timex, Tissot, Tudor, Tutima Glashütte, Ulysse Nardin,
Unimatic, Union Glashütte, Urwerk, Vacheron Constantin, Venezianico, Victorinox, Viqueria,
Vulcain, Wewood, Wood Star Milano, Woodstock Zambon, Wyler Vetta, Yema, Zenith, Zodiac,
Concord, Ebel, Lacoste, Tommy Hilfiger, Movado, Junghans, Maurice de Mauriac,
Sjöö Sandström, Halios, Farer, Mercer, Elliot Brown, Archimede, Stowa, Laco, Hanhart,
Mühle Glashütte, Zeppelin, Junkers, Prim, Tisell, Kopek, Christopher Ward, Steinhart,
Helson, Davosa, Bernhard H. Mayer, Louis Chevrolet, Giuliano Mazzuoli, Bering, Ice-Watch,
Sekonda, Accurist""",
    ),
    (
        "Moda e abbigliamento",
        "Dal lusso al fast fashion allo sportswear",
        """A-Cold-Wall, Acne Studios, Adidas, Aeance, A.P.C., Alexander McQueen, Alexander Wang,
Alfie Boe, Armani, Autry, Balenciaga, Balmain, Barbour, Berluti, Billionaire Boys Club,
Bogner, Bottega Veneta, Brunello Cucinelli, Burberry, Calvin Klein, Canada Goose, Carhartt,
Casablanca, Céline, Chanel, Chloé, Christian Louboutin, Comme des Garçons, Corneliani,
Courrèges, CP Company, Dior, Diesel, DKNY, Dolce & Gabbana, Dsquared2, Etro, Fendi,
Ferragamo, Filesofar, Fred Perry, Ganni, Givenchy, Golden Goose, Gucci, Helmut Lang, Hermès,
Hugo Boss, Issey Miyake, Isabel Marant, Jacquemus, Jil Sander, Jimmy Choo, Karl Lagerfeld,
Kenzo, Khrisjoy, Lacoste, Levi's, Liu Jo, Louis Vuitton, Lululemon, Maison Kitsuné,
Maison Margiela, Mango, Marc Jacobs, Marni, Max Mara, Michael Kors, Missoni, Miu Miu,
Moncler, Moschino, Napapijri, New Balance, Nike, The North Face, Off-White, Palm Angels,
Patagonia, Pinko, Polo Ralph Lauren, Prada, Premiata, Raf Simons, Ralph Lauren, Rick Owens,
Roberto Cavalli, Salvatore Ferragamo, Sandro, Sergio Rossi, Stella McCartney, Stone Island,
Supreme, Thom Browne, Tod's, Tom Ford, Tommy Hilfiger, Toteme, Trussardi, Valentino,
Versace, Vivienne Westwood, Woolrich, Y-3, Yohji Yamamoto, Zara, Bershka, Pull&Bear,
Stradivarius, Massimo Dutti, Oysho, Uniqlo, H&M, COS, Monki, ARKET, & Other Stories, Gap,
Banana Republic, J.Crew, Abercrombie & Fitch, Hollister, American Eagle, Guess, Esprit,
Pepe Jeans, G-Star Raw, 7 For All Mankind, True Religion, Wrangler, Lee, Tommy Jeans,
Superga, Converse, Vans, ASICS, Puma, Reebok, Fila, Ellesse, Champion, Umbro, Kappa,
Sergio Tacchini, Diadora, Le Coq Sportif, K-Way, Invicta, Benetton, Sisley, Marella,
Sportmax, MSGM, Patrizia Pepe, Elisabetta Franchi, Alberta Ferretti, Blumarine,
Philosophy di Lorenzo Serafini, Ermanno Scervino, Luisa Spagnoli, Brioni, Zegna, Canali,
Kiton, Loro Piana, Vitale Barberis Canonico, Boglioli, L.B.M 1911, Lardini, Tagliatore,
Slowear, Incotex, PT Torino""",
    ),
    (
        "Automotive",
        "Case automobilistiche e costruttori",
        """Abarth, Alfa Romeo, Aston Martin, Audi, Bentley, BMW, Bugatti, Cadillac, Chevrolet,
Chrysler, Citroën, Cupra, Dacia, Dallara, Dodge, DS Automobiles, Ferrari, Fiat, Ford,
Genesis, Honda, Hyundai, Infiniti, Jaguar, Jeep, Kia, Lamborghini, Lancia, Land Rover,
Lexus, Lincoln, Maserati, Mazda, McLaren, Mercedes-Benz, MG, Mini, Mitsubishi, Nissan,
Opel, Pagani, Peugeot, Porsche, RAM, Renault, Rolls-Royce, Seat, Skoda, Smart, Stellantis,
Subaru, Suzuki, Tesla, Toyota, Vauxhall, Volkswagen, Volvo, BYD, Chery, DFSK,
DR Automobiles, EMC, Geely, Great Wall, Haval, Lynk & Co, NIO, Polestar, Rivian, Lucid,
Fisker, Aiways, XPENG, Li Auto, Zeekr, Dongfeng, SAIC, GAC, Changan, BAIC, Maxus, LDV,
Isuzu, Hummer, GMC, Buick, Acura, Daihatsu, Mahindra, Tata, Maruti Suzuki, Force Motors,
Premier, Hindustan Motors, Zastava, Ariel, Caterham, Lotus, Morgan, Noble, TVR, Radical,
BAC, Bristol Cars, Wiesmann, Koenigsegg, Rimac, Pininfarina, Italdesign, Zenvo, Hennessey,
SSC North America, Mosler, De Tomaso, Iso Rivolta, Lister, Pantera, Qoros, Voyah, Seres,
ARCFOX, Leapmotor, Ora, Hongqi, Wey, Tank, Jetour, AITO, Deepal""",
    ),
    (
        "Computer e hardware",
        "Produttori di computer, laptop e componenti",
        """Acer, Apple, Asus, Chuwi, Dell, Dynabook, Fujitsu, Google, HP, Huawei, Lenovo, LG,
Microsoft, MSI, Panasonic, Razer, Samsung, Sony, Toshiba, Xiaomi, Gigabyte, Alienware,
OMEN by HP, Eluktronics, Framework, Clevo, Mechrevo, Hasee, Colorful, Medion, Teclast,
Jumper, Alldocube, Irbis, Prestigio, Packard Bell, Gateway, Compaq, IBM, NEC, Sharp, Epson,
Olivetti, Commodore, Atari, Amstrad""",
    ),
    (
        "Smartphone e telefonia",
        "Produttori di telefoni e dispositivi mobili",
        """Acer, AGM, Alcatel, Apple, Archos, Asus, BlackBerry, BQ, Caterpillar, Coolpad, Doogee,
Energizer, Fairphone, Gigaset, Google, Honor, Huawei, HMD Global, HTC, Infinix, Itel,
Kyocera, Lava, Leagoo, Lenovo, LG, Meizu, Motorola, Nokia, Nothing, Nubia, OnePlus, OPPO,
Oukitel, Poco, Panasonic, Realme, Redmagic, Redmi, Samsung, Sharp, Sony, TCL, Tecno,
Ulefone, Umidigi, Unihertz, Vivo, Wiko, Xiaomi, ZTE, iQOO, Teclast, Black Shark, Vertu,
Palm, Emporia, Doro, Crosscall, Shift, TechniSat, Medion, Brondi, Karbonn, Micromax,
Cubot, Blackview, Elephone, Vernee, Allview, Evolveo, Kruger&Matz, Cherry Mobile, MyPhone,
Starmobile, QMobile, BenQ""",
    ),
    (
        "Compagnie aeree",
        "Aviazione civile, di linea e low cost",
        """Aegean Airlines, Aer Lingus, Aeroflot, Aeromexico, Air Arabia, Air Astana, Air Canada,
Air China, Air Europa, Air France, Air India, Air Malta, Air Mauritius, Air New Zealand,
Air Serbia, Air Seychelles, Air Tahiti Nui, Air Transat, Alaska Airlines, ITA Airways,
All Nippon Airways, Allegiant Air, American Airlines, Asiana Airlines, Austrian Airlines,
Avianca, Azul Linhas Aéreas, Bangkok Airways, British Airways, Brussels Airlines,
Cathay Pacific, China Airlines, China Eastern, China Southern, Condor, Copa Airlines,
Croatia Airlines, Delta Air Lines, easyJet, Egyptair, El Al, Emirates, Ethiopian Airlines,
Etihad Airways, Eurowings, EVA Air, Finnair, Flydubai, flynas, Frontier Airlines,
Garuda Indonesia, GOL Linhas Aéreas, Gulf Air, Hawaiian Airlines, Iberia, IndiGo,
Icelandair, Japan Airlines, Jeju Air, Jet2, JetBlue, Jetstar, Jin Air, Kenya Airways, KLM,
Korean Air, LATAM Airlines, Lion Air, LOT Polish Airlines, Lufthansa, Malaysia Airlines,
Neos, Norwegian Air Shuttle, Oman Air, Pakistan International Airlines, Peach Aviation,
Philippine Airlines, Pobeda, Porter Airlines, Qantas, Qatar Airways, Ryanair,
Royal Jordanian, Royal Air Maroc, SAS Scandinavian Airlines, Shenzhen Airlines,
Singapore Airlines, SmartWings, South African Airways, Southwest Airlines, Spirit Airlines,
SriLankan Airlines, Swiss International Air Lines, TAP Air Portugal, Thai Airways,
TUI Airways, Turkish Airlines, United Airlines, Vietnam Airlines, Vistara, Vueling,
WestJet, Wizz Air, Xiamen Airlines, Zipair, Transavia, SunExpress, Volotea, SkyUp,
Binter Canarias, Iberia Express, Volaris, VivaAerobus, Air Baltic, Luxair, Belavia,
Pegasus Airlines, Corendon, Corsair International, French Bee, La Compagnie, Air Caraïbes,
Air Austral, ASL Airlines France, Windrose Airlines""",
    ),
    (
        "Tech, retail e largo consumo",
        "Piattaforme digitali, GDO, food & beverage",
        """Spotify, Netflix, Amazon, Google, Microsoft, Apple, Meta, TikTok, Snap, X, YouTube,
LinkedIn, WhatsApp, Telegram, Discord, Twitch, Zoom, Slack, Dropbox, Airbnb, Uber, Lyft,
Grab, Bolt, Lidl, Aldi, Carrefour, Esselunga, Conad, Coop, Spar, Pam Panorama, Bennet,
Decathlon, Ikea, MediaWorld, Unieuro, Euronics, Red Bull, Monster Energy, Rockstar Energy,
Coca-Cola, PepsiCo, Nestlé, Ferrero, Barilla, De Cecco, Mulino Bianco, Buitoni, Algida,
Magnum, Häagen-Dazs, Danone, Yoplait, Activia, Nutella, Kinder, Tic Tac, Mentos, Haribo,
Skittles, M&M's, Pringles, Lay's, Doritos""",
    ),
]


def norm(name: str) -> str:
    """Chiave di confronto: accenti via, minuscolo, spazi compattati."""
    ascii_only = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    )
    return " ".join(ascii_only.split()).lower()


def parse(blob: str) -> list[str]:
    """Da testo separato da virgole a lista pulita e deduplicata,
    mantenendo l'ordine originale."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in blob.replace("\n", " ").split(","):
        name = " ".join(raw.split())
        if not name:
            continue
        k = norm(name)
        if k in seen:
            continue
        seen.add(k)
        out.append(name)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="mostra cosa farebbe senza scrivere")
    ap.add_argument("--user-id", default=None,
                    help="id utente (default: il primo nel database)")
    args = ap.parse_args()

    db = SessionLocal()
    user = (
        db.get(models.User, args.user_id) if args.user_id
        else db.query(models.User).first()
    )
    if not user:
        print("Nessun utente nel database: crea prima il profilo dall'app.")
        return 1
    print(f"Profilo: {user.name} <{user.email}>\n")

    everywhere: dict[str, list[str]] = {}
    tot_new = tot_skip = 0

    for name, description, blob in COLLECTIONS:
        brands = parse(blob)
        for b in brands:
            everywhere.setdefault(norm(b), []).append(name)

        coll = (
            db.query(models.CompanyCollection)
            .filter(
                models.CompanyCollection.user_id == user.id,
                models.CompanyCollection.name == name,
            )
            .first()
        )
        if coll is None:
            coll = models.CompanyCollection(
                user_id=user.id, name=name, description=description
            )
            if not args.dry_run:
                db.add(coll)
                db.flush()

        existing = (
            {norm(m.name) for m in coll.members} if coll.id else set()
        )
        new = [b for b in brands if norm(b) not in existing]
        skipped = len(brands) - len(new)

        if not args.dry_run:
            for b in new:
                db.add(models.CompanyCollectionMember(
                    collection_id=coll.id, name=b, added_via="seed",
                ))
            db.commit()

        tot_new += len(new)
        tot_skip += skipped
        print(f"  {name:32s} {len(brands):4d} brand  "
              f"+{len(new):4d} nuovi  ={skipped:4d} già presenti")

    print(f"\nTotale: +{tot_new} aggiunti, {tot_skip} già presenti.")

    dupes = {k: v for k, v in everywhere.items() if len(set(v)) > 1}
    if dupes:
        print(f"\n{len(dupes)} brand compaiono in più liste (normale: un "
              f"marchio può operare in più settori). Esempi:")
        for k, v in sorted(dupes.items())[:12]:
            print(f"   {k:22s} -> {', '.join(sorted(set(v)))}")

    if args.dry_run:
        print("\n(dry-run: non è stato scritto niente)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
