import re
from typing import List, Tuple

class AcousticTextNormalizer:
    """
    Intelligent phonetic and acoustic text pre-processor for NCERT & STEM narration.
    
    Transforms textbook symbols, Greek characters, powers, fractions, and units into
    natural, effortless spoken English. Injects acoustic punctuation cues (breath pauses,
    inquisitive inflections, suspense ellipses) to elevate TTS from synthetic monotone to
    compelling, natural scientific storytelling.
    """

    # Units preceded by digits or numbers
    UNIT_MAPPINGS: List[Tuple[str, str]] = [
        # Acceleration & Velocity
        (r'(\d+(?:\.\d+)?)\s*m/s\^?2\b', r'\1 meters per second squared'),
        (r'(\d+(?:\.\d+)?)\s*m/s\b', r'\1 meters per second'),
        (r'(\d+(?:\.\d+)?)\s*km/h\b', r'\1 kilometers per hour'),
        (r'(\d+(?:\.\d+)?)\s*km/s\b', r'\1 kilometers per second'),
        (r'(\d+(?:\.\d+)?)\s*rad/s\b', r'\1 radians per second'),

        # Mass & Density
        (r'(\d+(?:\.\d+)?)\s*kg/m\^?3\b', r'\1 kilograms per cubic meter'),
        (r'(\d+(?:\.\d+)?)\s*kg\b', r'\1 kilograms'),
        (r'(\d+(?:\.\d+)?)\s*g\b', r'\1 grams'),
        (r'(\d+(?:\.\d+)?)\s*mg\b', r'\1 milligrams'),
        (r'(\d+(?:\.\d+)?)\s*μg\b', r'\1 micrograms'),

        # Distance & Length
        (r'(\d+(?:\.\d+)?)\s*km\b', r'\1 kilometers'),
        (r'(\d+(?:\.\d+)?)\s*cm\b', r'\1 centimeters'),
        (r'(\d+(?:\.\d+)?)\s*mm\b', r'\1 millimeters'),
        (r'(\d+(?:\.\d+)?)\s*μm\b', r'\1 micrometers'),
        (r'(\d+(?:\.\d+)?)\s*nm\b', r'\1 nanometers'),
        (r'(\d+(?:\.\d+)?)\s*pm\b', r'\1 picometers'),
        (r'(\d+(?:\.\d+)?)\s*Å\b', r'\1 angstroms'),

        # Time & Frequency
        (r'(\d+(?:\.\d+)?)\s*ns\b', r'\1 nanoseconds'),
        (r'(\d+(?:\.\d+)?)\s*μs\b', r'\1 microseconds'),
        (r'(\d+(?:\.\d+)?)\s*ms\b', r'\1 milliseconds'),
        (r'(\d+(?:\.\d+)?)\s*GHz\b', r'\1 gigahertz'),
        (r'(\d+(?:\.\d+)?)\s*MHz\b', r'\1 megahertz'),
        (r'(\d+(?:\.\d+)?)\s*kHz\b', r'\1 kilohertz'),
        (r'(\d+(?:\.\d+)?)\s*Hz\b', r'\1 hertz'),

        # Force, Energy & Power
        (r'(\d+(?:\.\d+)?)\s*kN\b', r'\1 kilonewtons'),
        (r'(\d+(?:\.\d+)?)\s*N\b', r'\1 newtons'),
        (r'(\d+(?:\.\d+)?)\s*GeV\b', r'\1 giga-electron-volts'),
        (r'(\d+(?:\.\d+)?)\s*MeV\b', r'\1 mega-electron-volts'),
        (r'(\d+(?:\.\d+)?)\s*keV\b', r'\1 kilo-electron-volts'),
        (r'(\d+(?:\.\d+)?)\s*eV\b', r'\1 electron-volts'),
        (r'(\d+(?:\.\d+)?)\s*MJ\b', r'\1 megajoules'),
        (r'(\d+(?:\.\d+)?)\s*kJ\b', r'\1 kilojoules'),
        (r'(\d+(?:\.\d+)?)\s*J\b', r'\1 joules'),
        (r'(\d+(?:\.\d+)?)\s*GW\b', r'\1 gigawatts'),
        (r'(\d+(?:\.\d+)?)\s*MW\b', r'\1 megawatts'),
        (r'(\d+(?:\.\d+)?)\s*kW\b', r'\1 kilowatts'),
        (r'(\d+(?:\.\d+)?)\s*W\b', r'\1 watts'),

        # Electricity & Magnetism
        (r'(\d+(?:\.\d+)?)\s*kV\b', r'\1 kilovolts'),
        (r'(\d+(?:\.\d+)?)\s*mV\b', r'\1 millivolts'),
        (r'(\d+(?:\.\d+)?)\s*V\b', r'\1 volts'),
        (r'(\d+(?:\.\d+)?)\s*kA\b', r'\1 kiloamperes'),
        (r'(\d+(?:\.\d+)?)\s*mA\b', r'\1 milliamperes'),
        (r'(\d+(?:\.\d+)?)\s*μA\b', r'\1 microamperes'),
        (r'(\d+(?:\.\d+)?)\s*A\b', r'\1 amperes'),
        (r'(\d+(?:\.\d+)?)\s*C\b', r'\1 coulombs'),
        (r'(\d+(?:\.\d+)?)\s*mC\b', r'\1 millicoulombs'),
        (r'(\d+(?:\.\d+)?)\s*μC\b', r'\1 microcoulombs'),
        (r'(\d+(?:\.\d+)?)\s*nC\b', r'\1 nanocoulombs'),
        (r'(\d+(?:\.\d+)?)\s*pC\b', r'\1 picocoulombs'),
        (r'(\d+(?:\.\d+)?)\s*MΩ\b', r'\1 mega-ohms'),
        (r'(\d+(?:\.\d+)?)\s*kΩ\b', r'\1 kilo-ohms'),
        (r'(\d+(?:\.\d+)?)\s*Ω\b', r'\1 ohms'),
        (r'(\d+(?:\.\d+)?)\s*μF\b', r'\1 microfarads'),
        (r'(\d+(?:\.\d+)?)\s*nF\b', r'\1 nanofarads'),
        (r'(\d+(?:\.\d+)?)\s*pF\b', r'\1 picofarads'),
        (r'(\d+(?:\.\d+)?)\s*F\b', r'\1 farads'),
        (r'(\d+(?:\.\d+)?)\s*mH\b', r'\1 millihenrys'),
        (r'(\d+(?:\.\d+)?)\s*μH\b', r'\1 microhenrys'),
        (r'(\d+(?:\.\d+)?)\s*H\b', r'\1 henrys'),
        (r'(\d+(?:\.\d+)?)\s*T\b', r'\1 tesla'),
        (r'(\d+(?:\.\d+)?)\s*Wb\b', r'\1 webers'),

        # Thermodynamics & Waves
        (r'(\d+(?:\.\d+)?)\s*°C\b', r'\1 degrees Celsius'),
        (r'(\d+(?:\.\d+)?)\s*°F\b', r'\1 degrees Fahrenheit'),
        (r'(\d+(?:\.\d+)?)\s*K\b', r'\1 kelvin'),
        (r'(\d+(?:\.\d+)?)\s*kPa\b', r'\1 kilopascals'),
        (r'(\d+(?:\.\d+)?)\s*Pa\b', r'\1 pascals'),
        (r'(\d+(?:\.\d+)?)\s*atm\b', r'\1 atmospheres'),
        (r'(\d+(?:\.\d+)?)\s*dB\b', r'\1 decibels'),
    ]

    # Academic abbreviations
    ABBREVIATION_MAPPINGS: List[Tuple[str, str]] = [
        (r'\be\.g\.,?\b', 'for example,'),
        (r'\bi\.e\.,?\b', 'that is,'),
        (r'\bvs\.\b|\bvs\b', 'versus'),
        (r'\betc\.\b|\betc\b', 'and so forth'),
        (r'\bapprox\.\b', 'approximately'),
        (r'\beqn\.\b|\beq\.\b', 'equation'),
        (r'\bfig\.\b', 'figure'),
        (r'\bref\.\b', 'reference'),
        (r'\bno\.\b', 'number'),
    ]

    # Common oratorical cues that benefit from an acoustic pause comma
    DRAMATIC_CUES = [
        "observe carefully",
        "behold",
        "consider this",
        "curiously",
        "remarkably",
        "in truth",
        "notice carefully",
        "picture this",
        "look closely",
        "let us reason together",
        "listen closely",
        "the secret is this",
        "fascinatingly",
        "astonishingly",
    ]

    @classmethod
    def clean_markdown_and_artifacts(cls, text: str) -> str:
        """Removes visual markdown, stage directions, and act headers from spoken text."""
        # Strip complete Act / Scene heading lines: "Act 1: The Hook", "**Act 1: Title**"
        text = re.sub(r'^(?:\*\*)?(?:Act|Scene)\s+\d+.*?(?:\*\*)?$', '', text, flags=re.IGNORECASE | re.MULTILINE)
        # Remove bold and italic markdown
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        # Remove markdown headers (#, ##, etc.)
        text = re.sub(r'#{1,6}\s*', '', text)
        # Remove backticks and inline code
        text = re.sub(r'`(.*?)`', r'\1', text)
        # Remove links: [text](url) -> text
        text = re.sub(r'\[(.*?)\]\([^)]*\)', r'\1', text)
        # Strip stage directions in square brackets: [pause], [dramatic music], [sfx: boom]
        text = re.sub(r'\[(?:pause|sfx|sound effect|music|laughter|applause|visual|b-roll)[^\]]*\]', '', text, flags=re.IGNORECASE)
        # Convert (pause) into an acoustic ellipsis
        text = re.sub(r'\(\s*pause\s*\)', '...', text, flags=re.IGNORECASE)
        # Strip parenthesized performance notes
        text = re.sub(r'\((?:whispering|excitedly|solemnly|smiling|curious|intrigued)\)', '', text, flags=re.IGNORECASE)
        # Remove residual Act / Scene prefixes inline
        text = re.sub(r'(?:Act|Scene)\s+\d+\s*[:\-—]\s*', '', text, flags=re.IGNORECASE)
        return text

    @classmethod
    def normalize_scientific_notation(cls, text: str) -> str:
        """Converts powers, scientific notation, and exponents into spoken phrasing."""
        # 3 x 10^8 or 3 × 10⁸ -> 3 times 10 to the 8th
        text = re.sub(r'(\d+(?:\.\d+)?)\s*[x×*]\s*10\^?([0-9]+)', r'\1 times 10 to the power of \2', text)
        text = re.sub(r'(\d+(?:\.\d+)?)\s*[x×*]\s*10\^?-([0-9]+)', r'\1 times 10 to the power of negative \2', text)
        text = re.sub(r'10\^?([0-9]+)', r'10 to the power of \1', text)
        text = re.sub(r'10\^?-([0-9]+)', r'10 to the power of negative \1', text)

        # Unicode superscripts
        text = text.replace('⁰', ' to the power of zero')
        text = text.replace('¹', '')
        text = text.replace('²', ' squared')
        text = text.replace('³', ' cubed')
        text = text.replace('⁴', ' to the fourth')
        text = text.replace('⁵', ' to the fifth')
        text = text.replace('⁶', ' to the sixth')
        text = text.replace('⁷', ' to the seventh')
        text = text.replace('⁸', ' to the eighth')
        text = text.replace('⁹', ' to the ninth')
        text = text.replace('⁻¹', ' inverse')
        text = text.replace('⁻²', ' to the negative two')

        # Caret powers: x^2 -> x squared, x^3 -> x cubed
        text = re.sub(r'\^2\b', ' squared', text)
        text = re.sub(r'\^3\b', ' cubed', text)
        text = re.sub(r'\^([0-9]+)\b', r' to the power of \1', text)

        # Fractions
        text = re.sub(r'\b1/2\b', 'one-half', text)
        text = re.sub(r'\b1/3\b', 'one-third', text)
        text = re.sub(r'\b1/4\b', 'one-fourth', text)
        text = re.sub(r'\b3/4\b', 'three-fourths', text)

        return text

    @classmethod
    def normalize_units(cls, text: str) -> str:
        """Expands physics and engineering units into clean spoken words."""
        for pattern, replacement in cls.UNIT_MAPPINGS:
            text = re.sub(pattern, replacement, text)
        return text

    @classmethod
    def normalize_greek_and_symbols(cls, text: str) -> str:
        """Phonetically translates mathematical and scientific symbols."""
        # Derivatives and rate of change
        text = re.sub(r'dΦ/dt', 'd phi by d t', text)
        text = re.sub(r'ΔΦ/Δt', 'delta phi over delta t', text)
        text = re.sub(r'dv/dt', 'd v by d t', text)
        text = re.sub(r'dx/dt', 'd x by d t', text)

        # Delta before variables (Δt, Δv, Δx, Δp)
        text = re.sub(r'Δ([A-Za-zΦ])', r'delta \1', text)
        text = text.replace('Δ', 'delta ')

        # Common physics greek letters
        greek_dict = {
            'α': ' alpha ',
            'β': ' beta ',
            'γ': ' gamma ',
            'ε': ' epsilon ',
            'ϵ': ' epsilon ',
            'θ': ' theta ',
            'λ': ' lambda ',
            'μ': ' micro ',
            'π': ' pi ',
            'ρ': ' rho ',
            'σ': ' sigma ',
            'τ': ' tau ',
            'φ': ' phi ',
            'Φ': ' phi ',
            'ω': ' omega ',
            'Ω': ' ohms ',
            'ħ': ' h-bar ',
        }
        for char, pron in greek_dict.items():
            text = text.replace(char, pron)

        # Mathematical operators
        text = text.replace('±', ' plus or minus ')
        text = text.replace('≈', ' is approximately ')
        text = text.replace('≠', ' does not equal ')
        text = text.replace('∝', ' is directly proportional to ')
        text = text.replace('≤', ' is less than or equal to ')
        text = text.replace('≥', ' is greater than or equal to ')
        text = text.replace('√', ' square root of ')
        text = text.replace('∫', ' the integral of ')
        text = text.replace('∑', ' the sum of ')
        text = text.replace('∞', ' infinity ')
        text = text.replace('×', ' times ')
        text = text.replace('÷', ' divided by ')

        # Equal signs in formulas: E = mc^2 -> E equals m c squared
        text = re.sub(r'(\b[A-Za-z])\s*=\s*', r'\1 equals ', text)
        text = re.sub(r'\s*=\s*', ' equals ', text)

        # Prevent 'at' from being read as the preposition when it's acceleration * time: 'a t'
        text = re.sub(r'\bplus\s+at\b', 'plus a t', text)
        text = re.sub(r'\b\+\s*at\b', 'plus a t', text)
        text = re.sub(r'\b\+\s*a\s*t\b', 'plus a t', text)

        # Prevent single-letter equation variables from blurring: e.g. "I squared R" -> "I squared R"
        # Ensure single capital letters have space around them
        text = re.sub(r'\b([A-Z])\s*\*\s*([A-Z])\b', r'\1 times \2', text)

        return text

    @classmethod
    def normalize_abbreviations(cls, text: str) -> str:
        """Expands textbook abbreviations."""
        for pattern, replacement in cls.ABBREVIATION_MAPPINGS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    @classmethod
    def inject_acoustic_pacing(cls, text: str) -> str:
        """
        Enhances prosody and respiratory cadence for EdgeTTS / Neural TTS.
        Ensures dramatic cues have commas for natural breath intake, and
        crucial suspense points have natural pauses.
        """
        # Single-pass regex with longest cues first
        sorted_cues = sorted(cls.DRAMATIC_CUES, key=len, reverse=True)
        joined_cues = '|'.join(re.escape(c) for c in sorted_cues)
        pattern = rf'(?i)(^|[.!?\n]\s*)({joined_cues})\b(\s*)([,:;—\.\?!])?'

        def _add_pause(m):
            prefix = m.group(1)
            cue_text = m.group(2)
            space = m.group(3)
            punc = m.group(4)
            if not punc:
                return f"{prefix}{cue_text}, "
            return m.group(0)

        text = re.sub(pattern, _add_pause, text)

        # Convert negative signs before math expressions: "equals -d phi" -> "equals negative d phi"
        text = re.sub(r'equals\s*-\s*([a-zA-Z0-9])', r'equals negative \1', text)

        # Clean redundant parentheticals like "12 volts (volts)" or "50 ohms (ohms)"
        text = re.sub(r'\b(\w+)\s*\(\1\b\)', r'\1', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(\w+)\s*\([A-Za-z]\)', r'\1', text)

        # Ensure sentence boundaries have clear double-space separation for breath pacing
        text = re.sub(r'([.?!])\s*([A-Z])', r'\1  \2', text)

        # Clean redundant spaces and punctuation
        text = re.sub(r'\s+,', ',', text)
        text = re.sub(r',+', ',', text)
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    @classmethod
    def normalize_for_speech(cls, text: str) -> str:
        """
        Master pipeline: cleans visual artifacts, translates formulas,
        expands units, and tunes acoustic cadence for crystal-clear spoken audio.
        """
        if not text:
            return ""

        text = cls.clean_markdown_and_artifacts(text)
        text = cls.normalize_abbreviations(text)
        text = cls.normalize_scientific_notation(text)
        text = cls.normalize_units(text)
        text = cls.normalize_greek_and_symbols(text)
        text = cls.inject_acoustic_pacing(text)

        return text
