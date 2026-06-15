"""
One-shot helper: parse pasted lineup CSV data, extract unique artist names,
merge with existing artists.txt, and write the updated file.
Run once then delete.
"""

import re
from pathlib import Path

HERE = Path(__file__).parent

RAW = r"""Lineup    Line-up (artiesten) (DB)
Unnamed record,Unnamed record,Unnamed record,Unnamed record



















Nørbak,Pariah,Wata Igarashi,Rødhåd,Polygonia,Abstract Division,JEANS,Nelly,Quelza,Cobahn,Human Space Machine,Eric Cloutier,Woody92    Nelly,Rødhåd,Abstract Division,Eric Cloutier,Wata Igarashi,JEANS,Nørbak,Quelza,Woody92,Polygonia,Cobahn,Pariah,Human Space Machine
Unnamed record,Unnamed record,Unnamed record    Makèz,Dennis Quin,Kerri Chandler
Joyhauser,MYRA,Bart Skils,Unnamed record,Unnamed record,Unnamed record    MYRA,Bart Skils,Joyhauser
Colyn    Colyn
Sunil Sharpe,u.r. trax,Paula Temple ,Vera Grace,Unnamed record,Unnamed record,Unnamed record,Unnamed record    u.r. trax,Paula Temple ,Vera Grace,Sunil Sharpe
Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Traumer,Morgan ,Noach,Luuk van Dijk ,Running Hot,Rossi.,D Stone ,Benjamin Berg,Juliana X
Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Alexia Glensy,Christian AB,Reiss,Malika,Francesco del Garda,Ben UFO
Ae:ther,Woo York ,Beswerda,8Kays,VNTM    Beswerda,Ae:ther,8Kays,Woo York ,VNTM
Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Shanti,Identified Patient,Celeste,Fafi Abdel Nour,Jasmín,Cinnaman,Marcel Dettmann,Casper Tielrooij,Nèna,Nala Brown
Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Tasha,Steffi,Beau Didier,Ben Sims,Alarico,ANNĒ
Unnamed record,Unnamed record,Unnamed record    Cubicolor,Maceo Plex,Franc Fala
Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Alex Kassian,Boris Coelman,Spacer Woman,Merve,Kyra Khaldi
De Sluwe Vos,Laidlaw,Benny Rodrigues,Newtone ,Chloé Robinson    Chloé Robinson,De Sluwe Vos,Benny Rodrigues,Laidlaw,Newtone
Unnamed record,Unnamed record,Unnamed record,Unnamed record    Budino,Cormac,Curses,Daniel Monaco

Spekki Webu,Efdemin,Garçon,Feral,Shoal,Luke Slater,Jephta,Laura BCR,Loek Frey,DJ Red,DJ Maria.,Anthony Linell,Talismann    Efdemin,Talismann,DJ Red,Anthony Linell,Luke Slater,Shoal,Laura BCR,Garçon,Loek Frey,Jephta,DJ Maria.,Spekki Webu,Feral
Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Luna,Cynthia Spiering,Vince,Pila,The Darkraver,Olive Anguz,Bass-D,Da Mouth of Madness
Kyle Starkey,Tjade,Jenny Cara,Essy    Essy,Kyle Starkey,Jenny Cara,Tjade
Cybersex,X CLUB.,Slimfit ,Jensen Interceptor,Lolsnake,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Cybersex,Lolsnake,X CLUB.,Jensen Interceptor

Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Ryan Elliott,Timo Nikson,Sansibar,Sandrien,Doudou MD,Anthony Parasole,Samuel Deep,Blasha & Allatt
CHEWCHEW,HUNEE,Aletha,Adam Pits ,Verity,Satoshi,DJ Marcelle,Tammo Hesselink,Virginia,Carlos Valdes,Oceanic,Naone ,Robert Bergman    Carlos Valdes,Virginia,Adam Pits ,Naone ,Aletha,Oceanic,Tammo Hesselink,Verity,HUNEE,DJ Marcelle,CHEWCHEW,Satoshi,Robert Bergman



Courtesy,MCR-T,Clara Cuvé,Baraka,ALCATRAZ,ALCATRAZ,Mietze Conte ,DJ Gigola ,Pablo Bozzi ,ace of demons,Mila Black    Pablo Bozzi ,DJ Gigola ,Baraka,Mila Black,ace of demons,Mietze Conte ,Courtesy,MCR-T,ALCATRAZ,Clara Cuvé

Tasha,Lea Occhi,Chlär,JSPRV35,Stephanie Sykes,TAFKAMP    Stephanie Sykes,Lea Occhi,Chlär,Tasha,TAFKAMP,JSPRV35
    Kalle Pablo,Juri Miralles,Cinema Royale,Tonno Disko,Barbara Boeing,Bibi Seck,Brass Rave Unit,Juliana X,Boris Coelman,Cromby,BELLA,Berkan V8,Trippy Tins,Lola Edo
Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Doudou MD,DPR,Reflex Blue,cap,DJ Senc,D'Julz,Samuel Deep,Christian AB,Coast 2 Coast
Charmaine,Chaos in The CBD,Daiki,Moxie,Antal,Daphni,Sisi,Charmaine,DJ Almelo,Margie,Kamma    Sisi,Moxie,Daphni,Daiki,DJ Almelo,Charmaine,Margie,Kamma,Chaos in The CBD,Antal
I-RO,Marcal,Comrade Winston,Rosati,Chrissie,Arthur Robert,Pink Concrete    Chrissie,I-RO,Pink Concrete,Comrade Winston,Rosati,Arthur Robert,Marcal
    Moxes,Emvae,Schwesta P,Baron Von Trax,YONES,Vera Moro,Hoesephine,PietNormaal,Desire
JEANS,Eva Vrijdag,spikey lee,lucia lu,acidheaven,cryptofauna,Yazzus,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    acidheaven,Eva Vrijdag,lucia lu,Yazzus,spikey lee,cryptofauna,JEANS
Sarkawt Hamad,JASSS,Soft Break ,Djrum,mad miran    Sarkawt Hamad,Soft Break ,mad miran,Djrum,JASSS
Unnamed record,Unnamed record,Unnamed record    DJ K,Rocinha,Mbé
Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Laurine,Nicolas Lutz,Hannecart,Paul Lution,Craig Richards,Midland,Gabbs,Among trees
Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Nacho,Mystral,Denver,Developer,Beatrice,Matrixxman,Aadja

Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Mateo Dufour,Alci,Traumer,Kai King,Toman
Regularfantasy,Marie Malarie ,Emmz,FAFF,Lewis Taylor,Tjade    Tjade,Lewis Taylor,Regularfantasy,FAFF,Marie Malarie ,Emmz


Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Carlos Valdes,Velasco,Cinnaman,Ron Obvious,Fonte,D. Tiffany,Samuel Deep,Mauro Moreno,Inoz,Sugar Free
Wispelturig,Ignez,Nick Moody,Sandrien,Ø [Phase]    Sandrien,Nick Moody,Ø [Phase],Ignez,Wispelturig
Diffrent,MALUGI,Helena Lauwaert,MALOU,Dangerous Dreaming,Moody Mehran,CRUSH3d,ferrari rot,Rozie,Spacer Woman,evin    Moody Mehran,evin,Helena Lauwaert,CRUSH3d,Dangerous Dreaming,Malugi,Rozie,Spacer Woman,ferrari rot,Diffrent,MALOU

Just Lauren,Recondite,VNTM,Mathew Jonson,Unnamed record    Recondite,VNTM,Mathew Jonson,Patrice Baumel,Just Lauren
Max Cooper,Nadia Struiwigh,Jasmín    Nadia Struiwigh,Jasmín,Max Cooper
Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Moopie,Combined Type ,Hannecart,Gene On Earth,cap,Reiss,Stella Zekri,Across Boundaries,Sonja Moonear,Noach,Automatic Writing

Perc,Lobster,Laura van Hal,Megan Leber,Colin Benders ,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Colin Benders ,Perc,Lobster,Laura van Hal,Megan Leber








Vera Logdanidi,French II,Hitam,Barker,Vardae,Olivia Mendez,Chami,NDRX,DVS1,Marco Shuttle,GiGi FM,Konduku,Andy Garvey,Nera,VRIL,Tammo Hesselink,JakoJako,D-Leria    Nera,D-Leria,DVS1,JakoJako,Tammo Hesselink,Barker,Konduku,Andy Garvey,French II,Hitam,Vardae,Vera Logdanidi,Marco Shuttle,VRIL,GiGi FM,Chami,Olivia Mendez,NDRX

Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Georgia,Dungeon Meat,Doudou MD,Samuel Deep,Daniele Temperilli,Carlita,Phone Traxxx,DJ Senc

Somewhen,Yoshiko,Bushbaby,Krampf,DJ Gigola ,Flansie,Nene H,angelboy,Dissolver,Paul Seul,Yung Singh,LB aka LABAT    Dissolver,LB aka LABAT,Yoshiko,Bushbaby,DJ Gigola ,Somewhen,Flansie,Nene H,Yung Singh,angelboy,Krampf,Paul Seul

Unnamed record,Unnamed record,Unnamed record    Alex Kassian,Fafi Abdel Nour,Parris
Selene,Altinbas,Dimi Angélis,Setaoc Mass,Justine Perry    Selene,Dimi Angélis,Altinbas,Justine Perry,Setaoc Mass
VIL,Stephanie Sykes,DAX J,Thomas P. Heckmann,UVB,Umwelt,Grace Dahl,CRAVO,Chontane    Dax J ,Chontane,UVB,Stephanie Sykes,Grace Dahl,Thomas P. Heckmann,Umwelt,VIL,CRAVO
TLM  Airlines    TLM  Airlines
DJ TOOL,mul/ANNA,Amanda Mussi,Kaiser,Yanamaste    mul/ANNA,Amanda Mussi,Kaiser,Yanamaste,DJ TOOL
Matisa ,Demi Riquísimo,Laidlaw,Kyra Khaldi ,Tsepo,Luuk van Dijk     Kyra Khaldi ,Demi Riquísimo,Tsepo,Luuk van Dijk ,Laidlaw,Matisa


DJ MELL G,Zenker Brothers,Woody92,Nala Brown,Philippa Pacho    Nala Brown,Zenker Brothers,Philippa Pacho,Woody92,DJ MELL G
VNTM,Philou Celaries,Marino Canal,Ae:ther    Philou Celaries,Marino Canal,VNTM,Ae:ther
Voigtmann,Locklead,Noach,Carlos Valdes,Tommy Chikara,Julian Anthony,Reiss    Reiss,Noach,Tommy Chikara,Locklead,Carlos Valdes,Julian Anthony,Voigtmann
Diora,Slimfit ,Jennifer Cardini,Juicy Romance,Bauernfeind ,Boys Noize,Ellen Allien ,Courtesy,ALCATRAZ,MRD,Daria Kolosova ,DJ Gigola ,MCR-T    DJ Gigola ,MCR-T,MRD,Jennifer Cardini,Boys Noize,Bauernfeind ,Slimfit ,Courtesy,ALCATRAZ,Juicy Romance,Ellen Allien ,Diora,Daria Kolosova
Ryan Elliott,Junki Inoue,Reiss,Shanti Celeste,Mia Cecille,Gabbs,Dresden,Peach,Ogazón ,PLO Man    Reiss,Peach,Ryan Elliott,Shanti Celeste,Ogazón ,PLO Man,Gabbs,Junki Inoue,Mia Cecille,Dresden
Aldonna,Audrey Danza,Spray ,Berkan V8,Amaliah,Sam Alfred,Maara,Tjade,Danielle    Tjade,Maara,Aldonna,Sam Alfred,Spray ,Berkan V8,Audrey Danza,Danielle,Amaliah
Coco Maria,Sassy J,Kléo,DJ Kampire,Kaidi Tatham ,Antal    Antal,Ron Trent,Kléo,Sassy J,Coco Maria,Kaidi Tatham ,Daniel Monaco
Serti,Oscar Mulero,Quelza,Reptant,Marco Shuttle,Dj Nobu,Garçon,Kia,Nelly,Jane Fitz,Sybil,Clarisa Kimskii    Serti,Clarisa Kimskii,Quelza,Dj Nobu,Oscar Mulero,Marco Shuttle,Jane Fitz,Nelly,Kia,Reptant,Garçon,Sybil
Superstrings,Unnamed record
ADIEL,P.E.A.R.L.,Carmen Electro,Héctor Oaks,Not A Headliner    Héctor Oaks,ADIEL,Carmen Electro,P.E.A.R.L.,Not A Headliner
Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Morgan ,Essets,Moxes,Berkan V8,Fais Le Beau,Moody Mehran,Freakenstein,DJ Killing
Mano Le Tough,Jasper Tygner,Weval,Aletha    Weval,Mano Le Tough,Jasper Tygner,Aletha
EMILIJA,Rozie,Dangerous Dreaming,Newtone ,DART
Speedy J,Lea Occhi,MARRØN,Najel,Mareena,Prance,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Speedy J,MARRØN,Mareena,Najel,Prance,Lea Occhi
Konstantin Sibold,Bart Skils    Bart Skils,Konstantin Sibold
ISAbella,Gerd Janson,Oceanic,HAAi    Gerd Janson,ISAbella,HAAi,Oceanic
Eva Vrijdag,Lin C,Surf 2 Glory ,Valeby,Spacer Woman,Helena Lauwaert
Cincity,Lerato Tsotetsi,Philou Louzolo,Rayzir    Philou Louzolo,Cincity
Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record    Craig Richards,Peach,Gabrielle Kwarteng,Christian AB,Quest,Carlita,Francesco del Garda,Helena Hauff,Carlos Valdes,Naone ,Harry McCanna,Doudou MD,The Ghost,Samuel Deep,Reiss
Unnamed record,Unnamed record,Unnamed record,Unnamed record    Jennifer Cardini
Tjade,SOLIT,Flo Massé,AIDA    Tjade,Flo Massé,AIDA,SOLIT

Liane,Temudo,Matrixxman,Fireground,Alarico,Laure Croft    Liane,Fireground,Alarico,Matrixxman,Temudo,Laure Croft
HUNEE,Antal    Antal,HUNEE

STERAC ,ROD,Megan Leber,KiNK,VNTM    VNTM,KiNK,STERAC ,ROD,Megan Leber

Julian Muller,CAIVA,Bebe Bad,MRD,Swimming Paul

Loek Frey,Shoal,Ogazón ,Spekki Webu,Priori,Stranger,Philippa Pacho,Roger Gerressen,DJ Pete,DJ Red,Djrum,Polygonia    Roger Gerressen,DJ Pete,Ogazón ,Stranger,Philippa Pacho,Spekki Webu,DJ Red,Priori,Loek Frey,Shoal,Polygonia,Djrum
Colin Benders ,Boris Acket
Mary Lake,Portrait XO
Oceanic,Sandrien,Enequist
Maarten Vos & Max Frimout,Polygonia
Samuel Deep,CARISTA,Robert Hood,Unnamed record,Unnamed record,Unnamed record

Juicy Romance,Schwesta P,Superstrings,Bae Blade,Unnamed record,Unnamed record
Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Unnamed record
Bart Skils,Victor Ruiz,Unnamed record
Lyrae ,Moxes,Ollie Lishman,Sophia Violet ,Miguel de Bois,Lennart,Queen Saba,Janis Zielinski  ,Rosa Red,Benwal,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
JEANS,Anetha ,VEL,A Strange Wedding,Mac Declos,DJ Leoni
Luna Ludmila,Kevin De Vries,Unnamed record,Unnamed record
Joris Voorn
Collabs 3000,Beste Hira
Move D,Margie,Ays,Danilo Plessow (MCDE),Unnamed record,Unnamed record,Unnamed record


Liam Palmer,Luuk van Dijk ,Naomi,Benjamin Berg,Elliot Schooling,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
CARISTA,Unnamed record

Partiboi69,Moxes,Loods,Maruwa,Unnamed record,Unnamed record
VNTM,Âme,Eli Verveine,Unnamed record,Unnamed record,Unnamed record
Djeff,Philou Louzolo,Jaden Thompson,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Bart Skils,Adam Beyer,Unnamed record,Unnamed record

Maï-Linh,Newtone ,Tjade,Julie Desire,Unnamed record,Unnamed record,Unnamed record

upsammy,Vera Logdanidi,Agonis,Dasha Rush,Aurora Halal,Bas Dobbelaer,DVS1,Oscar Mulero,Na Nich,OCCA,Seb H.,Aaron J,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
 Mella Dee,Noach,Luuk van Dijk ,Morgan ,Alex Kassian,Locklead,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Anz,Moxie,Sherelle,Chaos in The CBD,D Stone ,Byron Yeates,Bambounou,Bashkka,Courtesy,Naone ,Doudou MD,Unnamed record,Unnamed record,Unnamed record
Cobahn,Quelza,Hyperaktivist,Nene H,Delano Legito ,FJAAK,Jack Fresia,Fadi Mohem,Comrade Winston,I-RO,Planetary Assault Systems,Dr Rubinstein,Lobster,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record


Orpheu The Wizard,Parris,Kyra Khaldi ,Daphni,Berkan V8,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Superstrings,Bella Claxton,Faster Horses,CRUSH3d,SWIM ,Sex Wax,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record

HUNEE,Prins Thomas
Kikiorix,Daiki,Daiki,Luke Una,Kamma & Masalo,Sadar Bahar ,Ays,Antal,Gerd Janson,Unnamed record,Unnamed record,Unnamed record,Unnamed record
LUXE,John Talabot,Weval,Leon Vynehall,Alexia Glensy,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record

VNTM,Mano Le Tough,Recondite,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record




Steffi,Shoal & Vand,Efdemin,Eric Cloutier,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Tjade,Storm Mollison, Inafekt,MALOU,Spacer Woman,Olympe4000,Dan Shake ,Essy,Leo Sanderson,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record

Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record

Cassian,Rebuke,Hedda Stenberg,Tonco,VNTM,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Victoria De Angelis,angelboy,Cybersex,Daria Kolosova ,Patrick Mason,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record

Benny Rodrigues,Emvae,Sozef,22 Interns, Hidde van Wee,Enzo Jeff,Milion,Jimi Jua,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Rozie,Olivia Lensen,Freddi,Moody Mehran,Unnamed record,Unnamed record,Unnamed record,Unnamed record



BELLA,Uni Son,Grace Sands,Timmerman,LYLO,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record


Laurent Garnier,Steve Rachmad,Naone ,Unnamed record,Unnamed record,Unnamed record

Jane Fitz,Garçon,Talismann,nthng,Andy Garvey,Kessler,Oberman,Reptant,D.Dan,Konduku,Sandwell District,Costanza,JakoJako,Woody92,Eric Cloutier,Richard Akingbehin,Human Space Machine,Pariah,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record



Bradley Zero,Jordan Brando,Luuk van Dijk ,Bibi Seck,Elias Mazian
Jolani Jhones,Major Lazer,Kybba,Unnamed record,Unnamed record,Unnamed record


LSDXOXO,Travis,Raven,bebe bad,IFIF,Tsepo,Rob Black,Lola Edo,BIIANCO,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
HoneyLuv,LevyM,Syreeta,Philou Louzolo

Kurashi Soundsystem ,Sandor,Westside Gunn,LIL 'VIC,Tida Kamara,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record

Varuna Agosti,TWIENA,Parrish Smith,Ben Klock,DJ Pete,Hitam,Rosati,Mareena,Jesse G,Altinbas,Adriana Lopez,Amanda Mussi,Abstract Division,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Cincity,Collé,BLOND:ISH,Unnamed record,Unnamed record,Unnamed record


Florinsz,Reiss,Papa Nugs,Moxes,Emvae,Laura Meester,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Kaufman,Marco Faraone,S.A.M.,Bart Skils,Unnamed record
Jennifer Loveless ,Ploy,NIKS,Dyed Soundorom,Hervé,Anz,DJ Spit,Shonky,Kyra Khaldi ,Elias Mazian ,Doudou MD,DJ Fart in the Club,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Noach,Paramida,Tommy Chikara,Job de Jong,Sweely
Unnamed record,Unnamed record

Polygonia,Joya Astou,Prance,JEANS,Richie Hawtin,Olivia Mendez,MARRØN,Unnamed record
Gyatso,Tommy Gold,Richie Hawtin,Ignez,u.r. trax,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record

dj sweet6teen,D Stone ,PHIA,Luuk van Dijk ,Tsepo,Julian Anthony,Storm Mollison,Retromigration,Denis Sulta ,TSHA ,Unnamed record
mad miran,Christian AB,Pangaea,Amaliah,Ploy,Moopie,Naone ,Jorg Kuning (live),Impérieux,Ben UFO,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Interpol,THC,DART,Kyle Starkey,Bae Blade,Mordi,RONI,Match Box,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Antal,Tama Sumo , Louie Vega,HUNEE,Antal,Lakuti,Antal,Coco Maria,Unnamed record,Unnamed record,Unnamed record,Brandfee
Rødhåd,Serti,Xiaolin,Wata Igarashi,Sarkawt Hamad,DJ Red,Dj Nobu,GiGi FM,Objekt,Sepehr,Priori,CCL,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
KREAM,Unnamed record,Unnamed record,Unnamed record
VNTM,Unnamed record

Efdemin,Jasmín,Nene H,Colin Benders ,Quelza,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Joy Orbison ,CARISTA,BSS,Nick Leon,Unnamed record
Kléo,Richard Akingbehin,Marcel Dettmann,Pearson Sound,Peach,Prosumer,Antal,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record

DJ BORING,Gabriel Muñoz,LoveFoxy,Esi,Milion,Faster Horses,Unnamed record,Unnamed record,Unnamed record
Unnamed record
DJ Hyperdrive,Eva Vrijdag,VEL,DJ Shoplifter,Pegassi ,Swarobski,Justin Tinderdate,Elotrance,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Alexandria, Hidde van Wee,Anil Aras,Chris Stussy,Unnamed record,Unnamed record,Unnamed record,Unnamed record
HUNEE,Antal,Unnamed record,Unnamed record

Daria Kolosova ,Fumi,Technoslave 69,Lolsnake,ØTTA,BIIANCO,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Bambounou,Malindi,Tsepo,Boris Coelman,Gabrielle Kwarteng,TINS,Rozaly,Cormac,Bibtiana,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Aaron J,Andy Martin,Donato Dozzy,Nelly,Marius Bø,Oceanic,Paquita Gordon,Sandrien,Marco Shuttle,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Young Marco & Max Frimout,VRIL,Unnamed record,Unnamed record
JakoJako,Maarten Vos,Unnamed record,Unnamed record
Shoal,Dasha Rush,Spekki Webu,Unnamed record,Unnamed record,Unnamed record
Collé,Colyn,Unnamed record,Unnamed record

SAMOH,Carmen Lisa,Charlotte de Witte,Selene,Unnamed record,Unnamed record,Unnamed record
Mau P ,Unnamed record
Héctor Oaks,Vanille,Patrick Mason,Prance,Unnamed record,Unnamed record,Unnamed record
Tsepo,Dixon,Unnamed record,Unnamed record
Weska,Bart Skils,Boris Werner,Pan-Pot,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Bradley Zero,Kyra Khaldi ,Berkan V8,Sally C,Unnamed record,Unnamed record,Unnamed record,Unnamed record

Mall Grab,Mees Javois,Lola Edo,Unnamed record,Unnamed record
Tim Reaper,GiGi FM,Pariah,Darwin,DJ Pete,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Richie Hawtin,DVS1,Josey Rebelle,Samuel Deep,Unnamed record,Unnamed record,Unnamed record,Unnamed record
LINSKA,Kevin De Vries
Kara Okay,Paige Tomlinson,Julie Desire,Tjade,Paige Tomlinson,Unnamed record,Unnamed record
Philou Louzolo,Us Two,DAF,Bontan,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Bae Blade,X-COAST,YASMIN REGISFORD,EMILIJA,Essy,KTK,Supergloss,Unnamed record,Unnamed record,Unnamed record
Honey Dijon,Carlos Valdes,Unnamed record,Unnamed record

mad miran,Skee Mask,Luna Ludmila,Efdemin,Hysteria Temple Foundation ,Oscar Mulero,Polygonia,Jorge Fons,Altinbas,Timnah,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Floorplan,CARISTA,Makam,Unnamed record

JakoJako,VNTM,Gizem,Antonio Ruscito & Luigi Tozzi,Unnamed record,Unnamed record
Andrea Oliva,Cincity,Atmos Blaq,LevyM,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Isabel Soto,Speedy J,Claudio PRC,Megan Leber,Unnamed record,Unnamed record
Bakio,Hannecart,Voigtmann,J:Me,Benji,Noach,Marsolo,Phil de Janeiro,Julian Anthony,Job de Jong,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Mia Cecille,Sugar Free,Roza Terenzi,Bashkka,HUNEE,Bitter Babe,D.Tiffany,Roi Perez,Paquita Gordon,John Talabot,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Mind Against,Unnamed record
Kerrie,LazerGazer,BLANKA,Zisko,SAMA,Wata Igarashi,Julia Maria,Sarkawt Hamad,Amotik,Stojche,Karina Schneider,Delano Legito ,Function,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record

Hot Since 82,Kim April,Ranger Trucco,"Ranger Trucco, Kim April",Unnamed record,Test Joël,Karel

Unnamed record
DJ PAULÃO,Coco Maria,Musclecars,Kikiorix,Satoshi Tomiie,Giles Peterson,Antal,Kléo,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Unnamed record

Surf 2 Glory,Marlon Hoffstadt
Unnamed record
Marlon Hoffstadt,CVNTS,Sellout bonus Marlon,Saidah,Benny2
Agents of Time
Quelza,Quelza
Schwesta P,Unnamed record,Tjade,Unnamed record,Herr Krank,DJ Frank,Kendal,NewTone,Bella Claxton,Jenny Cara,Olivia Lensen,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record


nthng,VNTM,Luna Ludmila,Andy Martin,VRIL,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Cassian,Stranger,Re-Type,Tasha,Brina Knauss,REZarin,Joris Voorn,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Spacer Woman,CRYME,Matrixxman,Slimfit ,The Lady Machine,DJ Fuckoff,SALOME,PORNCEPTUAL,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record
Lilya Mandre,KUKU,MoBlack,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Laolu

Âme,Samaʼ Abdulhadi,Âme,Samaʼ Abdulhadi,Unnamed record,Unnamed record,Unnamed record,Unnamed record




Moody Mehran,Essy,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record



LSDXOXO,Fiene,BIIANCO,Supergloss,Unnamed record,Unnamed record



The Trip,Luuk van Dijk,DJ Boring,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Merel Helderman,Unnamed record

Tauceti,Polar Inertia,D.Dan,Kangding Ray,Faustin,DJ Yazi,JakoJako,Kia,Beatrice M.,Luke Vibert,Monophonik,Vlada,Innersha,Garcon,Agonis,Priori,oma totem,Spekki Webu,Sunju Hargun,Decoder


Philou Louzolo,Trikk,Yulia Niko,LYLO,Unnamed record,Unnamed record,Unnamed record
Unnamed record
Massano,Sellout
AMORAL,UFO95,Talismann,VIL,Valody,Tafkamp,Nick Moody,Mary Lake,Amanda Mussi,Toobris,BIANKA,Norbak,Olivia Mendez,Ignez,SECONDS (Setaoc Mass),SECONDS (Phara)

Bart Skils,Roger Geressen,Victor Ruiz,Oliver Huntemann,Hostingfee
Barker,Vera Logdanidi,Arthur Rober,Martinou,VNTM
Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record





Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record

Paquita Gordon,Christian AB,Francesco Del Garda,Marco Shuttle
Entasia,DART,Miamor,Tjade,Fiene,S3PPA,NewTone,Unnamed record,Unnamed record,Unnamed record,Unnamed record,THELMA
Ron Trent,Unnamed record,Antal
Andy Martin

Ryan Elliot,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record,Unnamed record





DAX J,Unnamed record




Unnamed record,Unnamed record

Antal,Hunee"""

SKIP = {"unnamed record", ""}

# Collect all names from both columns of every line
seen_lower = set()
names = []

for line in RAW.splitlines():
    # Split on 2+ spaces or tab to get left / right columns
    parts = re.split(r'  +|\t', line)
    # Gather all comma-separated tokens from all parts
    for part in parts:
        for token in part.split(','):
            name = token.strip().strip('"')
            # Drop parenthetical suffixes like "(live)", "(MCDE)"
            name = re.sub(r'\s*\(.*?\)\s*$', '', name).strip()
            # Skip garbage
            if not name or name.lower() in SKIP:
                continue
            # Skip obvious non-artist entries (header row)
            if name in ("Lineup", "Line-up (artiesten) (DB)"):
                continue
            # Skip things that are clearly event/act descriptors not artists
            if re.match(r'^(Sellout|Hostingfee|Test\s|Karel$|Benny2$)', name, re.I):
                continue
            key = name.lower()
            if key not in seen_lower:
                seen_lower.add(key)
                names.append(name)

# Load existing artists.txt
existing_path = HERE / "artists.txt"
existing_lines = [l.strip() for l in existing_path.read_text(encoding="utf-8").splitlines()]
existing_lower = {l.lower() for l in existing_lines if l}

# Find new additions
new_names = [n for n in names if n.lower() not in existing_lower]
print(f"Existing artists: {len(existing_lower)}")
print(f"New unique artists from lineup data: {len(new_names)}")
print(f"\nNew artists to add:")
for n in sorted(new_names, key=str.lower):
    safe = n.encode("ascii", "replace").decode("ascii")
    print(f"  {safe}")

# Append to artists.txt
with open(existing_path, "a", encoding="utf-8") as f:
    for n in new_names:
        f.write(n + "\n")

print(f"\nUpdated artists.txt — total artists: {len(existing_lower) + len(new_names)}")
