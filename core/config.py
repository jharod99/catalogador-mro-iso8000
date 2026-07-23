# Configuración Centralizada de Taxonomía y Reglas Industriales

FIELD_ABBREVIATIONS = [
    (r'\bF\s*°\s*F\s*°\b', 'FIERRO FUNDIDO'),
    (r'\bF\.F\.\b', 'FIERRO FUNDIDO'),
    (r'\bAC\s*/\s*INOX\b', 'ACERO INOXIDABLE'),
    (r'\bA\.INOX\b', 'ACERO INOXIDABLE'),
    (r'\bAC\s*/\s*C\b', 'ACERO AL CARBONO'),
]

ALLOWED_PRODUCTS = {
    "MECANICA": {"TUBERIA", "VALVULA", "BRIDA", "CODO", "CONEXION", "JUNTA", "SELLO", "ADAPTADOR", "ACOPLE"},
    "TI": {"CELULAR", "AURICULARES", "LAPTOP", "SERVIDOR", "COMPUTADORA", "MEMORIA", "DISCO", "TELEFONO", "SMARTPHONE", "AUDIFONOS", "AURICULAR", "SSD", "HDD", "NVME", "SOLID STATE"},
    "ELECTRICA": {"MOTOR", "INTERRUPTOR", "CABLE", "SENSOR", "TRANSMISOR", "CAUDALIMETRO"}
}

EXCLUDED_BOOST_KEYWORDS = {
    "acero", "carbono", "inoxidable", "hierro", "cobre", "bronce", "aluminio",
    "pvc", "hdpe", "ptfe", "plastico", "goma", "caucho", "silicona",
    "manguera", "tubo", "tubería", "placa", "lamina", "barra", "perfil",
    "gr", "grade", "grado", "b7", "2h", "f436", "astm", "clase", "tipo",
    "con", "sin", "para", "de", "con", "e", "y", "o", "u",
    "in", "plg", "mm", "cm", "m", "kg", "gr", "lb", "psi", "sch", "sdr",
    "unidades", "unidad", "piezas", "pieza", "accesorio", "accesorios",
    "componente", "componentes"
}

SYNONYM_MAP = {
    "esparrago": ["perno"],
    "esparragos": ["perno", "pernos"],
    "tubo": ["tuberia"],
    "tubos": ["tuberia", "tuberias"],
    "cañeria": ["tuberia"],
    "cañerias": ["tuberia", "tuberias"],
    "legion": ["computador", "laptop", "portatil"],
    "iphone": ["telefono", "celular", "movil"],
    "celular": ["celulares", "telefono", "telefonos", "movil", "moviles", "smartphone", "smartphones"],
    "telefono": ["telefonos", "celular", "celulares", "movil", "moviles", "smartphone", "smartphones"],
    "telefonos": ["telefono", "celular", "celulares", "movil", "moviles", "smartphone", "smartphones"],
    "celulares": ["celular", "telefono", "telefonos", "movil", "moviles", "smartphone", "smartphones"],
    "movil": ["moviles", "celular", "celulares", "telefono", "telefonos"],
    "moviles": ["movil", "celular", "celulares", "telefono", "telefonos"],
    "ssd": ["disco", "almacenamiento", "solido", "estado solido"],
    "disco ssd": ["disco", "almacenamiento", "solido", "estado solido"],
    "nvme": ["disco", "almacenamiento", "estado solido"],
    "hdd": ["disco", "almacenamiento", "disco duro"],
    "sockolet": ["accesorio de tuberia", "acoplamiento", "conexion", "fitting", "tuberia"],
    "weldolet": ["accesorio de tuberia", "acoplamiento", "conexion", "fitting", "tuberia"],
    "threadolet": ["accesorio de tuberia", "acoplamiento", "conexion", "fitting", "tuberia"],
    "olet": ["accesorio de tuberia", "acoplamiento", "conexion", "fitting", "tuberia"],
    "caudalimetro": ["flujometro", "medidor de flujo", "flowmeter", "transmisor de flujo", "sensor de flujo"],
    "flujometro": ["caudalimetro", "medidor de flujo", "flowmeter", "transmisor de flujo", "sensor de flujo"],
    "sensor": ["transmisor", "medidor", "detector", "indicador"],
    "transmisor": ["sensor", "medidor", "detector", "indicador"],
    "ventilador": ["fan", "soplador", "blower", "extractor"],
    "fan": ["ventilador", "soplador", "blower", "extractor"],
    "soplador": ["ventilador", "fan", "blower", "extractor"],
    "impresora": ["printer", "etiquetadora", "rotuladora", "rotulador"],
    "printer": ["impresora", "etiquetadora", "rotuladora", "rotulador"],
    "etiquetadora": ["impresora", "printer", "rotuladora", "rotulador"],
    "refrigeracion": ["enfriamiento", "enfriador", "chiller", "radiador", "intercambiador", "disipador"],
    "refrigeración": ["enfriamiento", "enfriador", "chiller", "radiador", "intercambiador", "disipador"],
    "enfriamiento": ["refrigeracion", "enfriador", "chiller", "radiador", "intercambiador", "disipador"],
    "chiller": ["enfriador", "refrigeracion", "intercambiador"],
    "radiador": ["enfriador", "refrigeracion", "intercambiador"]
}

NOUN_CLASS_MAPPING = {
    "perno": ["311615", "311616"],
    "esparrago": ["311615", "311616"],
    "tuerca": ["311617"],
    "arandela": ["311618"],
    "tuberia": ["401715", "4017", "4018"],
    "tubo": ["401715", "4017", "4018", "401416"],
    "tubos": ["401715", "4017", "4018", "401416"],
    "celular": ["431915"],
    "telefono": ["431915"],
    "teléfono": ["431915"],
    "smartphone": ["431915"],
    "laptop": ["432115"],
    "computadora": ["432115"],
    "computadora portatil": ["432115"],
    "computadora portátil": ["432115"],
    "computador": ["432115"],
    "portatil": ["432115"],
    "portátil": ["432115"],
    "ssd": ["432018"],
    "disco": ["432018"],
    "disco ssd": ["432018"],
    "disco solido": ["432018"],
    "disco sólido": ["432018"],
    "disco duro": ["432018"],
    "unidad de estado solido": ["432018"],
    "unidad de estado sólido": ["432018"],
    "solid state drive": ["432018"],
    "accesorio": ["4014", "4017"],
    "accesorio de tuberia": ["4014", "4017"],
    "accesorio de tubería": ["4014", "4017"],
    "accesorio para tuberia": ["4014", "4017"],
    "accesorio_para_tuberia": ["4014", "4017"],
    "accesorio_de_tuberia": ["4014", "4017"],
    "sockolet": ["4014", "4017"],
    "weldolet": ["4014", "4017"],
    "threadolet": ["4014", "4017"],
    "olet": ["4014", "4017"],
    "caudalimetro": ["411125", "411033"],
    "flujometro": ["411125", "411033"],
    "sensor": ["411119", "411125", "4111"],
    "transmisor": ["411125", "4111"],
    "ventilador": ["401016"],
    "fan": ["401016"],
    "soplador": ["401016"],
    "impresora": ["432121"],
    "printer": ["432121"],
    "etiquetadora": ["432121"],
    "refrigeracion": ["401017", "401018", "251726", "321310", "432015"],
    "refrigeración": ["401017", "401018", "251726", "321310", "432015"],
    "enfriamiento": ["401017", "401018", "251726", "321310", "432015"],
    "radiador": ["401018", "251726", "251918"],
    "chiller": ["401017"],
    "disipador": ["321310", "432015"],
    "motor": ["261011", "261012", "2610"],
    "motores": ["261011", "261012", "2610"]
}

MARCAS_COMUNES = ["HUAWEI", "APPLE", "LENOVO", "CATERPILLAR", "SKF", "DEMTECH", "DELL", "HP", "SIEMENS", "ABB", "FESTO", "SMC", "ZEBRA", "SAMSUNG", "WD", "WESTERN DIGITAL", "KINGSTON", "CRUCIAL", "SWAGELOK", "SAB", "XIAOMI"]

EQUIPOS_COMPLETOS = ["CELULAR", "AURICULARES", "BOMBA", "MOTOR", "LAPTOP", "IMPRESORA", "CHANCADORA", "VENTILADOR"]

INDICADORES_REPUESTO = ["PARTES O ACCESORIOS DE", "REPUESTOS DE", "ACCESORIOS PARA", "PARTES DE"]

DIAMETROS_COMERCIALES = [0.25, 0.375, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 24.0, 30.0, 32.0, 34.0, 36.0, 40.0, 42.0, 48.0]
DIAMETROS_MM_COMERCIALES = [16, 20, 25, 32, 40, 50, 63, 75, 90, 110, 160, 200, 250, 315, 400, 450, 500, 630]

BODY_MATERIALS = [
    ("FIERRO FUNDIDO", "FIERRO FUNDIDO"),
    ("HIERRO FUNDIDO", "HIERRO FUNDIDO"),
    ("HIERRO DUCTIL", "HIERRO DUCTIL"),
    ("CAST IRON", "HIERRO FUNDIDO"),
    ("DUCTILE IRON", "HIERRO DUCTIL"),
    ("BRONCE", "BRONCE"),
]
