import os
from abc import ABC, abstractmethod
from typing import Optional, List
from copy import deepcopy
from autode.log import logger
from autode.input_output import xyz_file_to_atoms
from autode.exceptions import SolventNotFound


def get_solvent(solvent_name: str,
                kind:         str,
                num:          Optional[int] = None) -> Optional['Solvent']:
    """
    For a named solvent return the Solvent which matches one of the aliases

    ---------------------------------------------------------------------------
    Arguments:
        solvent_name (str): Name of the solvent e.g. DCM. Not case sensitive

        kind (str): Kind of solvent. One of: {"implicit", "explicit"}

    Keyword Arguments:
        num (int | None): Number of explicit solvent molecules to include in
                          the explicit solvent

    Returns:
        (autode.solvent.solvents.Solvent | None): Solvent

    Raises:
        (ValueError): If both explicit and implicit solvent are selected
    """
    kind = kind.lower()

    if kind not in ('explicit', 'implicit'):
        raise ValueError(f'Solvent must be explicit or implicit. Had: {kind}')

    if solvent_name is None:
        logger.warning('Not requested any solvent - returning None')
        return None

    if kind == 'explicit' and num is None:
        raise ValueError('Requested an explicit solvent but number of explicit'
                         ' solvent molecules was not defined')

    for solvent in solvents:

        # Comparisons of solvents are not case sensitive
        if solvent_name.lower() not in solvent.aliases:
            continue

        if solvent.is_implicit:
            return solvent if kind == 'implicit' else solvent.to_explicit(num=num)

        # Allow for solvent.is_explicit in solvents?

    raise SolventNotFound('No matching solvent in the library for '
                          f'{solvent_name}')


class Solvent(ABC):

    def __init__(self,
                 name:    str,
                 smiles:  Optional[str] = None,
                 aliases: Optional[List[str]] = None,
                 **kwargs):
        """
        Abstract base class for a solvent. As electronic structure methods
        implement implicit solvation without a unique list of solvents there
        needs to be conversion between them, while also allowing for user
        specifying one possibility from a list of aliases

        ----------------------------------------------------------------------
        Arguments:
            name (str): Unique name of the solvent

            smiles (str | None): SMILES string

            aliases (list(str) | None): Different names for the same solvent
                                       e.g. water and H2O. If None then will
                                       only use the name as an alias

        Keyword Arguments:
            kwargs (str): Name of the solvent in the electronic structure
                          package e.g. Solvent(..., orca='water')
        """

        self.name = name
        self.smiles = smiles
        self.aliases = [name.lower()]

        if aliases is not None:
            self.aliases.extend(alias.lower() for alias in aliases)

        # Add attributes for all the methods specified e.g. initialisation with
        # orca='water' -> self.orca = 'water'
        self.__dict__.update(kwargs)

        # Gaussian 09 and Gaussian 16 solvents are named the same
        if 'g09' in kwargs.keys():
            self.g16 = kwargs['g09']

    def __repr__(self):
        return f'Solvent({self.name})'

    def __str__(self):
        return self.name

    def __eq__(self, other):
        """Determine if two solvents are the same based on name and SMILES"""
        if other is None:
            return False

        return self.name == other.name and self.smiles == other.smiles

    def copy(self) -> 'Solvent':
        """Return a copy of this solvent"""
        return deepcopy(self)

    @property
    def dielectric(self) -> Optional[float]:
        """
        Dielectric constant (ε) of this solvent. Used in implicit solvent
        models to determine the electrostatic interaction

        Returns:
            (float | None): Dielectric, or None if unknown
        """
        for alias in self.aliases:
            if alias in _solvents_and_dielectrics:
                return _solvents_and_dielectrics[alias]

        logger.warning(f'Could not find a dielectric for: {self}. '
                       f'Returning None')
        return None

    @property
    @abstractmethod
    def is_implicit(self) -> bool:
        """Is this solvent implicit and just defined by a dielectric"""

    @property
    def is_explicit(self) -> bool:
        """Is this solvent explicit i.e. has atoms in space"""
        return not self.is_implicit


class ImplicitSolvent(Solvent):
    """Implicit solvent"""

    @property
    def is_implicit(self) -> bool:
        """Is this solvent implicit?

        Returns:
            (bool): True
        """
        return True

    def to_explicit(self, num: int) -> 'autode.solvent.ExplicitSolvent':
        """
        Convert this implicit solvent into an explicit one

        -----------------------------------------------------------------------
        Arguments:
            num (int): Number of explicit solvent molecules to include

        Raises:
            (IOError): If the expected 3D structure cannot be located

        Returns:
            (autode.solvent.explicit_solvent.ExplicitSolvent): Solvent
        """
        from autode.species.species import Species           # cyclic imports..
        from autode.solvent.explicit_solvent import ExplicitSolvent

        here = os.path.dirname(os.path.abspath(__file__))
        xyz_path = os.path.join(here, 'lib', f'{self.name}.xyz')

        if not os.path.exists(xyz_path):
            raise IOError(f'Could not convert {self.name} to explicit solvent '
                          f'{xyz_path} did not exist')

        # Solvent must be neutral and with a spin multiplicity of one
        solvent_mol = Species(name=self.name,
                              charge=0,
                              mult=1,
                              atoms=xyz_file_to_atoms(xyz_path))

        return ExplicitSolvent(solvent=solvent_mol, num=num,
                               solute=None, aliases=self.aliases)


solvents = [ImplicitSolvent(name='water', smiles='O', aliases=['water', 'h2o'], orca='water', g09='Water', nwchem='water', xtb='Water', mopac='water', qchem='water'),
            ImplicitSolvent(name='dichloromethane', smiles='ClCCl', aliases=['dichloromethane', 'methyl dichloride', 'dcm'], orca='dichloromethane', g09='Dichloromethane', nwchem='dcm', xtb='CH2Cl2', mopac='dichloromethane', qchem='dichloromethane'),
            ImplicitSolvent(name='acetone', smiles='CC(C)=O', aliases=['acetone', 'propanone'], orca='acetone', g09='Acetone', nwchem='acetone', xtb='Acetone', mopac='acetone', qchem='acetone'),
            ImplicitSolvent(name='acetonitrile', smiles='CC#N', aliases=['acetonitrile', 'mecn', 'ch3cn'], orca='acetonitrile', g09='Acetonitrile', nwchem='acetntrl', xtb='Acetonitrile', mopac='acetonitrile', qchem='acetonitrile'),
            ImplicitSolvent(name='benzene', smiles='C1=CC=CC=C1', aliases=['benzene', 'cyclohexatriene'], orca='benzene', g09='Benzene', nwchem='benzene', xtb='Benzene', mopac='benzene', qchem='benzene'),
            ImplicitSolvent(name='trichloromethane', smiles='ClC(Cl)Cl', aliases=['chloroform', 'trichloromethane', 'chcl3', 'methyl trichloride'], orca='chloroform', g09='Chloroform', nwchem='chcl3', xtb='CHCl3', mopac='chloroform', qchem='trichloromethane'),
            ImplicitSolvent(name='cs2', smiles='S=C=S', aliases=['cs2', 'methanedithione', 'carbon bisulfide'], orca='carbon disulfide', g09='CarbonDiSulfide', nwchem='cs2', xtb='CS2', mopac='cs2', qchem='carbon disulfide'),
            ImplicitSolvent(name='dmf', smiles='O=CN(C)C', aliases=['dmf', 'dimethylformamide', 'n,n-dimethylformamide'], orca='n,n-dimethylformamide', g09='n,n-DiMethylFormamide', nwchem='dmf', xtb='DMF', mopac='n,n-dimethylformamide', qchem='dimethylformamide'),
            ImplicitSolvent(name='dmso', smiles='O=S(C)C', aliases=['dmso', 'dimethylsulfoxide'], orca='dimethylsulfoxide', g09='DiMethylSulfoxide', nwchem='dmso', xtb='DMSO', mopac='dmso'),
            ImplicitSolvent(name='diethyl ether', smiles='CCOCC', aliases=['diethyl ether', 'ether', 'Ethoxyethane'], orca='diethyl ether', g09='DiethylEther', nwchem='ether', xtb='Ether', mopac='ether', qchem='diethyl ether'),
            ImplicitSolvent(name='methanol', smiles='CO', aliases=['methanol', 'meoh'], orca='methanol', g09='Methanol', nwchem='methanol', xtb='Methanol', mopac='methanol', qchem='ethanol'),
            ImplicitSolvent(name='hexane', smiles='CCCCCC', aliases=['hexane', 'n-hexane'], orca='n-hexane', g09='n-Hexane', nwchem='hexane', xtb='n-Hexane', mopac='hexane', qchem='hexane'),
            ImplicitSolvent(name='thf', smiles='C1CCOC1', aliases=['thf', 'tetrahydrofuran', 'oxolane'], orca='tetrahydrofuran', g09='TetraHydroFuran', nwchem='thf', xtb='THF', mopac='tetrahydrofuran', qchem='tetrahydrofuran'),
            ImplicitSolvent(name='toluene', smiles='CC1=CC=CC=C1', aliases=['toluene', 'methylbenzene', 'phenyl methane'], orca='toluene', g09='Toluene', nwchem='toluene', xtb='Toluene', mopac='toluene', qchem='benzene'),
            ImplicitSolvent(name='acetic acid', smiles='CC(O)=O', aliases=['acetic acid', 'ethanoic acid'], orca='acetic acid', g09='AceticAcid', nwchem='acetacid', mopac='acetic acid', qchem='acetic acid'),
            ImplicitSolvent(name='1-butanol', smiles='CCCCO', aliases=['1-butanol', 'butanol', 'n-butanol', 'butan-1-ol'], orca='1-butanol', g09='1-Butanol', nwchem='butanol', mopac='1-butanol', qchem='1-butanol'),
            ImplicitSolvent(name='2-butanol', smiles='CC(O)CC', aliases=['2-butanol', 'sec-butanol', 'butan-2-ol'], orca='2-butanol', g09='2-Butanol', nwchem='butanol2', mopac='2-butanol', qchem='sec-butanol'),
            ImplicitSolvent(name='acetophenone', smiles='CC(C1=CC=CC=C1)=O', aliases=['acetophenone', 'phenylacetone', 'phenylethanone'], orca='acetophenone', g09='AcetoPhenone', nwchem='acetphen', mopac='acetophenone', qchem='acetone'),
            ImplicitSolvent(name='aniline', smiles='NC1=CC=CC=C1', aliases=['aniline', 'benzenamine', 'phenylamine'], orca='aniline', g09='Aniline', nwchem='aniline', mopac='aniline', qchem='aniline'),
            ImplicitSolvent(name='anisole', smiles='COC1=CC=CC=C1', aliases=['anisole', 'methoxybenzene', 'phenoxymethane'], orca='anisole', g09='Anisole', nwchem='anisole', mopac='anisole', qchem='anisole'),
            ImplicitSolvent(name='benzaldehyde', smiles='O=CC1=CC=CC=C1', aliases=['benzaldehyde', 'phenylmethanal'], orca='benzaldehyde', g09='Benzaldehyde', nwchem='benzaldh', mopac='benzaldehyde', qchem='benzaldehyde'),
            ImplicitSolvent(name='benzonitrile', smiles='N#CC1=CC=CC=C1', aliases=['benzonitrile', 'cyanobenzene', 'phenyl cyanide'], orca='benzonitrile', g09='BenzoNitrile', nwchem='benzntrl', mopac='benzonitrile', qchem='benzene'),
            ImplicitSolvent(name='benzyl chloride', smiles='ClCC1=CC=CC=C1', aliases=['benzyl chloride', '(chloromethyl)benzene', 'Chloromethyl benzene', 'a-chlorotoluene'], orca='a-chlorotoluene', g09='a-ChloroToluene', nwchem='benzylcl', mopac='benzyl chloride', qchem='benzene'),
            ImplicitSolvent(name='1-bromo-2-methylpropane', smiles='CC(C)CBr', aliases=['1-bromo-2-methylpropane', 'isobutyl bromide'], orca='1-bromo-2-methylpropane', g09='1-Bromo-2-MethylPropane', nwchem='brisobut', mopac='isobutyl bromide', qchem='1-bromo-2-methylpropane'),
            ImplicitSolvent(name='bromobenzene', smiles='BrC1=CC=CC=C1', aliases=['bromobenzene', 'phenyl bromide'], orca='bromobenzene', g09='BromoBenzene', nwchem='brbenzen', mopac='bromobenzene', qchem='benzene'),
            ImplicitSolvent(name='bromoethane', smiles='CCBr', aliases=['bromoethane', 'ethyl bromide', 'etbr'], orca='bromoethane', g09='BromoEthane', nwchem='brethane', mopac='bromoethane', qchem='bromoethane'),
            ImplicitSolvent(name='bromoform', smiles='BrC(Br)Br', aliases=['bromoform', 'tribromomethane', 'methyl tribromide', 'chbr3'], orca='bromoform', g09='Bromoform', nwchem='bromform', mopac='bromoform', qchem='tribromomethane'),
            ImplicitSolvent(name='1-bromooctane', smiles='CCCCCCCCBr', aliases=['1-bromooctane', 'bromooctane', 'octyl bromide', '1-octyl bromide'], orca='1-bromooctane', g09='1-BromoOctane', nwchem='broctane', mopac='bromooctane', qchem='bromooctane'),
            ImplicitSolvent(name='1-bromopentane', smiles='CCCCCBr', aliases=['1-bromopentane', 'bromopentane', 'pentyl bromide'], orca='1-bromopentane', g09='1-BromoPentane', nwchem='brpentan', mopac='bromopentane', qchem='1-bromopentane'),
            ImplicitSolvent(name='butantal', smiles='CCCC=O', aliases=['butanal', 'butyraldehyde'], orca='butanal', g09='Butanal', nwchem='butanal', mopac='butanal', qchem='butanal'),
            ImplicitSolvent(name='butanone', smiles='CC(CC)=O', aliases=['butanone', '2-butanone', 'butan-2-one', 'methyl ethyl ketone', 'ethyl methyl ketone'], orca='butanone', g09='Butanone', nwchem='butanone', mopac='2-butanone', qchem='butanone'),
            ImplicitSolvent(name='carbon tetrachloride', smiles='ClC(Cl)(Cl)Cl', aliases=['carbon tetrachloride', 'ccl4', 'tetrachloromethane'], orca='carbon tetrachloride', g09='CarbonTetraChloride', nwchem='carbntet', mopac='carbon tetrachloride', qchem='carbon tetrachloride'),
            ImplicitSolvent(name='chlorobenzene', smiles='ClC1=CC=CC=C1', aliases=['chlorobenzene', 'benzene chloride', 'phenyl chloride'], orca='chlorobenzene', g09='ChloroBenzene', nwchem='clbenzen', mopac='chlorobenzene', qchem='benzene'),
            ImplicitSolvent(name='cyclohexane', smiles='C1CCCCC1', aliases=['cyclohexane'], orca='cyclohexane', g09='CycloHexane', nwchem='cychexan', mopac='cyclohexane', qchem='cyclohexane'),
            ImplicitSolvent(name='1,2-dichlorobenzene', smiles='ClC1=CC=CC=C1Cl', aliases=['1,2-dichlorobenzene', 'o-dichlorobenzene', 'ortho-dichlorobenzene'], orca='o-dichlorobenzene', g09='o-DiChloroBenzene', nwchem='odiclbnz', mopac='1,2-dichlorobenzene', qchem='benzene'),
            ImplicitSolvent(name='n,n-dimethylacetamide', smiles='CC(N(C)C)=O', aliases=['n,n-dimethylacetamide', 'dmac', 'dma', 'dimethylacetamide'], orca='n,n-dimethylacetamide', g09='n,n-DiMethylAcetamide', nwchem='dma', mopac='n,n-dimethylacetamide', qchem='dimethylacetamide'),
            ImplicitSolvent(name='dioxane', smiles='O1CCOCC1', aliases=['dioxane', '1,4-dioxane', 'p-dioxane'], orca='1,4-dioxane', g09='1,4-Dioxane', nwchem='dioxane', mopac='1,4-dioxane', qchem='1,4-dioxane'),
            ImplicitSolvent(name='ethyl acetate', smiles='CC(OCC)=O', aliases=['ethyl acetate', 'etoac', 'ethyl ethanoate'], orca='ethyl ethanoate', g09='EthylEthanoate', nwchem='etoac', mopac='ethyl acetate'),
            ImplicitSolvent(name='ethanol', smiles='CCO', aliases=['ethanol', 'ethyl alcohol', 'etoh'], orca='ethanol', g09='Ethanol', nwchem='ethanol', mopac='ethyl alcohol', qchem='ethanol'),
            ImplicitSolvent(name='heptane', smiles='CCCCCCC', aliases=['heptane', 'n-heptane'], orca='n-heptane', g09='Heptane', nwchem='heptane', mopac='heptane', qchem='heptane'),
            ImplicitSolvent(name='pentane', smiles='CCCCC', aliases=['pentane', 'n-pentane'], orca='n-pentane', g09='n-Pentane', nwchem='npentane', mopac='pentane', qchem='pentane'),
            ImplicitSolvent(name='1-propanol', smiles='CCCO', aliases=['1-propanol', 'propanol', 'n-propaol', 'n-proh'], orca='1-propanol', g09='1-Propanol', nwchem='propanol', mopac='1-propanol', qchem='1-propanol'),
            ImplicitSolvent(name='pyridine', smiles='C1=NC=CC=C1', aliases=['pyridine'], orca='pyridine', g09='Pyridine', nwchem='pyridine', mopac='pyridine', qchem='pyridine'),
            ImplicitSolvent(name='1,1,1-trichloroethane', smiles='CC(Cl)(Cl)Cl', aliases=['1,1,1-trichloroethane', 'methyl chloroform', '1,1,1-tca'], orca='1,1,1-trichloroethane', g09='1,1,1-TriChloroEthane', nwchem='tca111', mopac='1,1,1-trichloroethane', qchem='1,1,1-trichloroethane'),
            ImplicitSolvent(name='cyclopentane', smiles='C1CCCC1', aliases=['cyclopentane'], orca='cyclopentane', g09='CycloPentane', nwchem='cycpentn', mopac='cyclopentane', qchem='cyclopentane'),
            ImplicitSolvent(name='1,1,2-trichloroethane', smiles='ClCC(Cl)Cl', aliases=['1,1,2-trichloroethane', 'vinyl trichloride', '1,1,2-tca'], orca='1,1,2-trichloroethane', g09='1,1,2-TriChloroEthane', nwchem='tca112', mopac='1,1,2-trichloroethane', qchem='1,1,2-trichloroethane'),
            ImplicitSolvent(name='cyclopentanol', smiles='OC1CCCC1', aliases=['cyclopentanol'], orca='cyclopentanol', g09='CycloPentanol', nwchem='cycpntol', mopac='cyclopentanol', qchem='cyclopentanol'),
            ImplicitSolvent(name='1,2,4-trimethylbenzene', smiles='CC1=CC=C(C)C(C)=C1', aliases=['1,2,4-trimethylbenzene', 'pseudocumene'], orca='1,2,4-trimethylbenzene', g09='1,2,4-TriMethylBenzene', nwchem='tmben124', mopac='1,2,4-trimethylbenzene', qchem='1,2,4-trimethylbenzene'),
            ImplicitSolvent(name='cyclopentanone', smiles='O=C1CCCC1', aliases=['cyclopentanone'], orca='cyclopentanone', g09='CycloPentanone', nwchem='cycpnton', mopac='cyclopentanone', qchem='cyclopentanone'),
            ImplicitSolvent(name='1,2-dibromoethane', smiles='BrCCBr', aliases=['1,2-dibromoethane', 'ethylene dibromide', 'edb'], orca='1,2-dibromoethane', g09='1,2-DiBromoEthane', nwchem='edb12', mopac='1,2-dibromoethane', qchem='bromoethane'),
            ImplicitSolvent(name='1,2-dichloroethane', smiles='ClCCCl', aliases=['1,2-dichloroethane', 'ethylene dichloride', 'dce', 'dichloroethane'], orca='1,2-dichloroethane', g09='DiChloroEthane', nwchem='edc12', mopac='1,2-dichloroethane'),
            ImplicitSolvent(name='cis-decalin', smiles='[H][C@@]12CCCC[C@]1([H])CCCC2', aliases=['cis-decalin', 'cis decalin'], orca='cis-decalin', g09='Cis-Decalin', nwchem='declncis', mopac='cis-decalin', qchem='decalin'),
            ImplicitSolvent(name='trans-decalin', smiles='[H][C@@]12CCCC[C@@]1([H])CCCC2', aliases=['trans-decalin', 'trans decalin'], orca='trans-decalin', g09='trans-Decalin', nwchem='declntra', mopac='trans-decalin', qchem='decalin'),
            ImplicitSolvent(name='decalin mix', smiles='C12CCCCC1CCCC2', aliases=['decalin mix', 'decalin', 'decalin mixture'], orca='decalin', g09='Decalin-mixture', nwchem='declnmix', mopac='decalin', qchem='decalin'),
            ImplicitSolvent(name='1,2-ethanediol', smiles='OCCO', aliases=['1,2-ethanediol', 'ethylene glycol', 'ethane-1,2-diol', 'monoethylene glycol'], orca='1,2-ethanediol', g09='1,2-EthaneDiol', nwchem='meg', mopac='1,2-ethanediol', qchem='ethylene glycol'),
            ImplicitSolvent(name='decane', smiles='CCCCCCCCCC', aliases=['decane', 'n-decane'], orca='n-decane', g09='n-Decane', nwchem='decane', mopac='decane', qchem='decane'),
            ImplicitSolvent(name='dibromomethane', smiles='BrCBr', aliases=['dibromomethane', 'methyl dibromide'], orca='dibromomethane', g09='DiBromomEthane', nwchem='dibrmetn', mopac='dibromomethane', qchem='dibromomethane'),
            ImplicitSolvent(name='dibutylether', smiles='CCCCOCCCC', aliases=['dibutylether', 'butyl ether'], orca='dibutylether', g09='DiButylEther', nwchem='butyleth', mopac='dibutylether'),
            ImplicitSolvent(name='cis-1,2-dichloroethene', smiles='Cl/C=C\\Cl', aliases=['cis-1,2-dichloroethene', 'cis-1,2-dichloroethylene', 'z-1,2-dichloroethene','z-1,2-dichloroethylene'], orca='z-1,2-dichloroethene', g09='z-1,2-DiChloroEthene', nwchem='c12dce', mopac='z-1,2-dichloroethene', qchem='z-1,2-dichloroethene'),
            ImplicitSolvent(name='trans-1,2-dichloroethen', smiles='Cl/C=C/Cl', aliases=['trans-1,2-dichloroethene', 'trans-1,2-dichloroethylene', 'e-1,2-dichloroethene', 'e-1,2-dichloroethylene'], orca='e-1,2-dichloroethene', g09='e-1,2-DiChloroEthene', nwchem='t12dce', mopac='z-1,2-dichloroethene', qchem='E-1,2-dichloroethene'),
            ImplicitSolvent(name='1-bromopropane', smiles='CCCBr', aliases=['1-bromopropane', 'bromopropane'], orca='1-bromopropane', g09='1-BromoPropane', nwchem='brpropan', mopac='1-bromopropane', qchem='1-bromopropane'),
            ImplicitSolvent(name='2-bromopropane', smiles='CC(Br)C', aliases=['2-bromopropane', 'isopropyl bromide'], orca='2-bromopropane', g09='2-BromoPropane', nwchem='brpropa2', mopac='2-bromopropane', qchem='2-bromopropane'),
            ImplicitSolvent(name='1-chlorohexane', smiles='CCCCCCCl', aliases=['1-chlorohexane', 'chlorohexane'], orca='1-chlorohexane', g09='1-ChloroHexane', nwchem='clhexane', mopac='1-chlorohexane', qchem='hexane'),
            ImplicitSolvent(name='1-chloropentane', smiles='CCCCCCl', aliases=['1-chloropentane', 'chloropentane'], orca='1-chloropentane', g09='1-ChloroPentane', nwchem='clpentan', mopac='1-chloropentane', qchem='1-chloropentane'),
            ImplicitSolvent(name='1-chloropropane', smiles='CCCCl', aliases=['1-chloropropane', 'chloropropane'], orca='1-chloropropane', g09='1-ChloroPropane', nwchem='clpropan', mopac='1-chloropropane', qchem='1-chloropropane'),
            ImplicitSolvent(name='diethylamine', smiles='CCNCC', aliases=['diethylamine', 'n-ethylethanamine'], orca='diethylamine', g09='DiEthylAmine', nwchem='dietamin', mopac='diethylamine', qchem='diethylamine'),
            ImplicitSolvent(name='1-decanol', smiles='CCCCCCCCCCO', aliases=['1-decanol', 'decanol', 'decan-1-ol'], orca='1-decanol', g09='1-Decanol', nwchem='decanol', mopac='decanol', qchem='1-decanol'),
            ImplicitSolvent(name='diiodomethane', smiles='ICI', aliases=['diiodomethane', 'methylene iodide'], orca='diiodomethane', g09='DiIodoMethane', nwchem='mi', mopac='diiodomethane', qchem='diiodomethane'),
            ImplicitSolvent(name='1-fluorooctane', smiles='CCCCCCCCF', aliases=['1-fluorooctane', 'fluorooctane', 'octyl fluoride'], orca='1-fluorooctane', g09='1-FluoroOctane', nwchem='foctane', mopac='1-fluorooctane', qchem='1-fluorooctane'),
            ImplicitSolvent(name='1-heptanol', smiles='CCCCCCCO', aliases=['1-helptanol', 'heptanol', 'heptan-1-ol'], orca='1-helptanol', g09='1-Heptanol', nwchem='heptanol', mopac='heptanol', qchem='1-heptanol'),
            ImplicitSolvent(name='cis-1,2-dimethylcyclohexane', smiles='C[C@@H]1[C@H](C)CCCC1', aliases=['cis-1,2-dimethylcyclohexane'], orca='cis-1,2-dimethylcyclohexane', g09='Cis-1,2-DiMethylCycloHexane', nwchem='cisdmchx', mopac='cisdmchx', qchem='cis-1,2-dimethylcyclohexane'),
            ImplicitSolvent(name='diethyl sulfide', smiles='CCSCC', aliases=['diethyl sulfide', 'et2s', 'thioethyl ether'], orca='diethyl sulfide', g09='DiEthylSulfide', nwchem='et2s', mopac='diethyl sulfide'),
            ImplicitSolvent(name='diisopropyl ether', smiles='CC(OC(C)C)C', aliases=['diisopropyl ether', 'dipe'], orca='diisopropyl ether', g09='DiIsoPropylEther', nwchem='dipe', mopac='diisopropyl ether', qchem='isopropyl ether'),
            ImplicitSolvent(name='1-hexanol', smiles='CCCCCCO', aliases=['1-hexanol', 'hexanol', 'haxan-1-ol'], orca='1-hexanol', g09='1-Hexanol', nwchem='hexanol', mopac='hexanol', qchem='1-hexanol'),
            ImplicitSolvent(name='1-hexene', smiles='C=CCCCC', aliases=['1-hexene', 'hexene', 'hex-1-ene'], orca='1-hexene', g09='1-Hexene', nwchem='hexene', mopac='hexene', qchem='1-hexene'),
            ImplicitSolvent(name='1-hexyne', smiles='C#CCCCC', aliases=['1-hexyne', 'hexyne', 'hex-1-yne'], orca='1-hexyne', g09='1-Hexyne', nwchem='hexyne', mopac='hexyne', qchem='1-hexyne'),
            ImplicitSolvent(name='1-iodobutane', smiles='CCCCI', aliases=['1-iodobutane', 'iodobutane'], orca='1-iodobutane', g09='1-IodoButane', nwchem='iobutane', mopac='iodobutane', qchem='1-iodobutane'),
            ImplicitSolvent(name='1-iodohexadecane', smiles='CCCCCCCCCCCCCCCCI', aliases=['1-iodohexadecane', 'iodohexadecane'], orca='1-iodohexadecane', g09='1-IodoHexaDecane', nwchem='iohexdec', mopac='1-iodohexadecane', qchem='decane'),
            ImplicitSolvent(name='diphenylether', smiles='C1(OC2=CC=CC=C2)=CC=CC=C1', aliases=['diphenylether', 'phenoxybenzene'], orca='diphenylether', g09='DiPhenylEther', nwchem='phoph', mopac='diphenylether', qchem='benzene'),
            ImplicitSolvent(name='1-iodopentane', smiles='CCCCCI', aliases=['1-iodopentane', 'iodopentane'], orca='1-iodopentane', g09='1-IodoPentane', nwchem='iopentan', mopac='1-iodopentane', qchem='pentane'),
            ImplicitSolvent(name='1-iodopropane', smiles='CCCI', aliases=['1-iodopropane', 'iodopropane'], orca='1-iodopropane', g09='1-IodoPropane', nwchem='iopropan', mopac='1-iodopropane', qchem='1-iodopropane'),
            ImplicitSolvent(name='dipropylamine', smiles='CCCNCCC', aliases=['dipropylamine'], orca='dipropylamine', g09='DiPropylAmine', nwchem='dproamin', mopac='dipropylamine', qchem='dipropylamine'),
            ImplicitSolvent(name='n-dodecane', smiles='CCCCCCCCCCCC', aliases=['n-dodecane', 'dodecane'], orca='n-dodecane', g09='n-Dodecane', nwchem='dodecan', mopac='dodecane', qchem='decane'),
            ImplicitSolvent(name='1-nitropropane', smiles='CCC[N+]([O-])=O', aliases=['1-nitropropane'], orca='1-nitropropane', g09='1-NitroPropane', nwchem='ntrprop1', mopac='1-nitropropane', qchem='1-nitropropane'),
            ImplicitSolvent(name='ethanethiol', smiles='CCS', aliases=['ethanethiol', 'ethane thiol', 'etsh'], orca='ethanethiol', g09='EthaneThiol', nwchem='etsh', mopac='ethanethiol', qchem='ethanethiol'),
            ImplicitSolvent(name='1-nonanol', smiles='CCCCCCCCCO', aliases=['1-nonanol', 'nonanol', 'nonan-1-ol'], orca='1-nonanol', g09='1-Nonanol', nwchem='nonanol', mopac='nonanol', qchem='1-nonanol'),
            ImplicitSolvent(name='1-octanol', smiles='CCCCCCCCO', aliases=['1-octanol', 'octanol', 'octan-1-ol'], orca='1-octanol', g09='n-Octanol', nwchem='octanol', mopac='octanol', qchem='1-octanol'),
            ImplicitSolvent(name='1-pentanol', smiles='CCCCCO', aliases=['1-pentanol', 'pentanol', 'pentan-1-ol'], orca='1-pentanol', g09='1-Pentanol', nwchem='pentanol', mopac='pentanol', qchem='1-pentanol'),
            ImplicitSolvent(name='1-pentene', smiles='C=CCCC', aliases=['1-pentene', 'pentene', 'pent-1-ene'], orca='1-pentene', g09='1-Pentene', nwchem='pentene', mopac='pentene', qchem='1-pentene'),
            ImplicitSolvent(name='ethyl benzene', smiles='CCC1=CC=CC=C1', aliases=['ethyl benzene', 'ethylbenzene', 'phenylethane'], orca='ethylbenzene', g09='EthylBenzene', nwchem='eb', mopac='ethylbenzene', qchem='benzene'),
            ImplicitSolvent(name='2,2,2-trifluoroethanol', smiles='FC(F)(F)CO', aliases=['2,2,2-trifluoroethanol'], orca='2,2,2-trifluoroethanol', g09='2,2,2-TriFluoroEthanol', nwchem='tfe222', mopac='2,2,2-trifluoroethanol', qchem='ethanol'),
            ImplicitSolvent(name='fluorobenzene', smiles='FC1=CC=CC=C1', aliases=['fluorobenzene', 'phenyl fluoride', 'c6h5f'], orca='fluorobenzene', g09='FluoroBenzene', nwchem='c6h5f', mopac='fluorobenzene', qchem='benzene'),
            ImplicitSolvent(name='2,2,4-trimethylpentane', smiles='CC(C)(C)CC(C)C', aliases=['2,2,4-trimethylpentane', 'isooctane'], orca='2,2,4-trimethylpentane', g09='2,2,4-TriMethylPentane', nwchem='isoctane', mopac='2,2,4-trimethylpentane', qchem='2,2,4-trimethylpentane'),
            ImplicitSolvent(name='formamide', smiles='O=CN', aliases=['formamide'], orca='formamide', g09='Formamide', nwchem='formamid', mopac='formamide', qchem='formamide'),
            ImplicitSolvent(name='2,4-dimethylpentane', smiles='CC(C)CC(C)C', aliases=['2,4-dimethylpentane', 'diisopropylmethane'], orca='2,4-dimethylpentane', g09='2,4-DiMethylPentane', nwchem='dmepen24', mopac='2,4-dimethylpentane', qchem='2,4-dimethylpentane'),
            ImplicitSolvent(name='2,4-dimethylpyridine', smiles='CC1=CC(C)=NC=C1', aliases=['2,4-dimethylpyridine', '2,4-lutidine'], orca='2,4-dimethylpyridine', g09='2,4-DiMethylPyridine', nwchem='dmepyr24', mopac='2,4-dimethylpyridine', qchem='2,4-dimethylpyridine'),
            ImplicitSolvent(name='2,6-dimethylpyridine', smiles='CC1=CC=CC(C)=N1', aliases=['2,6-dimethylpyridine', '2,6-lutidine', 'lutidine'], orca='2,6-dimethylpyridine', g09='2,6-DiMethylPyridine', nwchem='dmepyr26', mopac='2,6-dimethylpyridine', qchem='2,6-dimethylpyridine'),
            ImplicitSolvent(name='n-hexadecane', smiles='CCCCCCCCCCCCCCCC', aliases=['n-hexadecane', 'hexadecane'], orca='n-hexadecane', g09='n-Hexadecane', nwchem='hexadecn', mopac='hexadecane', qchem='decane'),
            ImplicitSolvent(name='dimethyl disulfide', smiles='CSSC', aliases=['dimethyl disulfide', 'dmds', 'methyl disulfide'], orca='dimethyl disulfide', g09='DiMethylDiSulfide', nwchem='dmds', mopac='dimethyl disulfide'),
            ImplicitSolvent(name='ethyl methanoate', smiles='O=COCC', aliases=['ethyl methanoate', 'ethyl formate', 'etome'], orca='ethyl methanoate', g09='EthylMethanoate', nwchem='etome', mopac='ethyl methanoate'),
            ImplicitSolvent(name='ethyl phenyl ether', smiles='CCOC1=CC=CC=C1', aliases=['ethyl phenyl ether', 'phenetole', 'ethoxybenzene'], orca='ethyl phenyl ether', g09='EthylPhenylEther', nwchem='phentol', mopac='phenetole', qchem='benzene'),
            ImplicitSolvent(name='formic acid', smiles='O=CO', aliases=['formic acid', 'methanoic acid'], orca='formic acid', g09='FormicAcid', nwchem='formacid', mopac='formic acid', qchem='formic acid'),
            ImplicitSolvent(name='hexanoic acid', smiles='CCCCCC(O)=O', aliases=['hexanoic acid', 'caproic acid'], orca='hexanoic acid', g09='HexanoicAcid', nwchem='hexnacid', mopac='hexanoic acid', qchem='hexanoic acid'),
            ImplicitSolvent(name='2-chlorobutane', smiles='CC(Cl)CC', aliases=['2-chlorobutane', 'sec-butyl chloride'], orca='2-chlorobutane', g09='2-ChloroButane', nwchem='secbutcl', mopac='2-chlorobutane', qchem='2-chlorobutane'),
            ImplicitSolvent(name='2-heptanone', smiles='CC(CCCCC)=O', aliases=['2-heptanone', 'heptan-2-one'], orca='2-heptanone', g09='2-Heptanone', nwchem='heptnon2', mopac='2-heptanone', qchem='2-heptanone'),
            ImplicitSolvent(name='2-hexanone', smiles='CC(CCCC)=O', aliases=['2-hexanone', 'hexan-2-one'], orca='2-hexanone', g09='2-Hexanone', nwchem='hexanon2', mopac='2-hexanone', qchem='2-hexanone'),
            ImplicitSolvent(name='2-methoxyethanol', smiles='COCCO', aliases=['2-methoxyethanol', 'egme'], orca='2-methoxyethanol', g09='2-MethoxyEthanol', nwchem='egme', mopac='2-methoxyethanol', qchem='ethanol'),
            ImplicitSolvent(name='2-methyl-1-propanol', smiles='CC(C)CO', aliases=['2-methyl-1-propanol', 'isobutanol'], orca='2-methyl-1-propanol', g09='2-Methyl-1-Propanol', nwchem='isobutol', mopac='isobutanol', qchem='1-propanol'),
            ImplicitSolvent(name='2-methyl-2-propanol', smiles='CC(O)(C)C', aliases=['2-methyl-2-propanol', 'tert-butanol'], orca='2-methyl-2-propanol', g09='2-Methyl-2-Propanol', nwchem='terbutol', mopac='tertbutanol', qchem='2-propanol'),
            ImplicitSolvent(name='2-methylpentane', smiles='CC(C)CCC', aliases=['2-methylpentane', 'isohexane'], orca='2-methylpentane', g09='2-MethylPentane', nwchem='isohexan', mopac='2-methylpentane', qchem='2-methylpentane'),
            ImplicitSolvent(name='2-methylpyridine', smiles='CC1=NC=CC=C1', aliases=['2-methylpyridine', '2-picoline'], orca='2-methylpyridine', g09='2-MethylPyridine', nwchem='mepyrid2', mopac='2-methylpyridine', qchem='2-methylpyridine'),
            ImplicitSolvent(name='2-nitropropane', smiles='CC([N+]([O-])=O)C', aliases=['2-nitropropane'], orca='2-nitropropane', g09='2-NitroPropane', nwchem='ntrprop2', mopac='2-nitropropane', qchem='2-nitropropane'),
            ImplicitSolvent(name='2-octanone', smiles='CC(CCCCCC)=O', aliases=['2-octanone', 'octan-2-one'], orca='2-octanone', g09='2-Octanone', nwchem='octanon2', mopac='2-octanone', qchem='2-octanone'),
            ImplicitSolvent(name='2-pentanone', smiles='CC(CCC)=O', aliases=['2-pentanone', 'pentan-2-one'], orca='2-pentanone', g09='2-Pentanone', nwchem='pentnon2', mopac='2-pentanone', qchem='2-pentanone'),
            ImplicitSolvent(name='iodobenzene', smiles='IC1=CC=CC=C1', aliases=['iodobenzene', 'phenyl iodide'], orca='iodobenzene', g09='IodoBenzene', nwchem='c6h5i', mopac='iodobenzene', qchem='benzene'),
            ImplicitSolvent(name='iodoethane', smiles='CCI', aliases=['iodoethane', 'ethyl iodide'], orca='iodoethane', g09='IodoEthane', nwchem='c2h5i', mopac='iodoethane', qchem='iodoethane'),
            ImplicitSolvent(name='iodomethane', smiles='CI', aliases=['iodomethane', 'methyl iodide', 'mei', 'ch3i'], orca='iodomethane', g09='IodoMethane', nwchem='ch3i', mopac='iodomethane', qchem='iodomethane'),
            ImplicitSolvent(name='isopropylbenzene', smiles='CC(C1=CC=CC=C1)C', aliases=['isopropylbenzene', 'cumene'], orca='isopropylbenzene', g09='IsoPropylBenzene', nwchem='cumene', mopac='isopropylbenzene', qchem='benzene'),
            ImplicitSolvent(name='p-isopropyltoluene', smiles='CC1=CC=C(C(C)C)C=C1', aliases=['p-isopropyltoluene', 'para-isopropyltoluene', 'p-cymene'], orca='p-isopropyltoluene', g09='p-IsoPropylToluene', nwchem='p-cymene', mopac='p-cymene', qchem='isopropyltoluene'),
            ImplicitSolvent(name='mesitylene', smiles='CC1=CC(C)=CC(C)=C1', aliases=['mesitylene'], orca='mesitylene', g09='Mesitylene', nwchem='mesityln', mopac='mesitylene', qchem='mesitylene'),
            ImplicitSolvent(name='methyl benzoate', smiles='O=C(OC)C1=CC=CC=C1', aliases=['methyl benzoate'], orca='methyl benzoate', g09='MethylBenzoate', nwchem='mebnzate', mopac='methyl benzoate'),
            ImplicitSolvent(name='methyl butanoate', smiles='CCCC(OC)=O', aliases=['methyl butanoate', 'methyl butyrate'], orca='methyl butanoate', g09='MethylButanoate', nwchem='mebutate', mopac='methyl butanoate'),
            ImplicitSolvent(name='methyl ethanoate', smiles='CC(OC)=O', aliases=['methyl ethanoate', 'methyl acetate'], orca='methyl ethanoate', g09='MethylEthanoate', nwchem='meacetat', mopac='methyl acetate'),
            ImplicitSolvent(name='methyl methanoate', smiles='O=COC', aliases=['methyl methanoate', 'methyl formate'], orca='methyl methanoate', g09='MethylMethanoate', nwchem='meformat', mopac='methyl formate'),
            ImplicitSolvent(name='methyl propanoate', smiles='CCC(OC)=O', aliases=['methyl propanoate', 'methyl propionate'], orca='methyl propanoate', g09='MethylPropanoate', nwchem='mepropyl', mopac='methyl propanoate'),
            ImplicitSolvent(name='n-methylaniline', smiles='CNC1=CC=CC=C1', aliases=['n-methylaniline', 'nma'], orca='n-methylaniline', g09='n-MethylAniline', nwchem='nmeaniln', mopac='n-methylaniline', qchem='aniline'),
            ImplicitSolvent(name='methylcyclohexane', smiles='CC1CCCCC1', aliases=['methylcyclohexane'], orca='methylcyclohexane', g09='MethylCycloHexane', nwchem='mecychex', mopac='methylcyclohexane', qchem='cyclohexane'),
            ImplicitSolvent(name='n-methylformamide (e/z mixture)', smiles='O=CNC', aliases=['n-methylformamide', 'n-methylformamide (e/z mixture)', 'n-methylformamide mixture', 'n-methylformamide mix'], orca='n-methylformamide (e/z mixture)', g09='n-MethylFormamide-mixture', nwchem='nmfmixtr', mopac='nmfmixtr', qchem='formamide'),
            ImplicitSolvent(name='nitrobenzene', smiles='O=[N+](C1=CC=CC=C1)[O-]', aliases=['nitrobenzene', 'phno2'], orca='nitrobenzene', g09='NitroBenzene', nwchem='c6h5no2', mopac='nitrobenzene', qchem='benzene'),
            ImplicitSolvent(name='nitroethane', smiles='CC[N+]([O-])=O', aliases=['nitroethane', 'etno2'], orca='nitroethane', g09='NitroEthane', nwchem='c2h5no2', mopac='nitroethane', qchem='nitroethane'),
            ImplicitSolvent(name='nitromethane', smiles='C[N+]([O-])=O', aliases=['nitromethane', 'meno2', 'ch3no2'], orca='nitromethane', g09='NitroMethane', nwchem='ch3no2', mopac='nitromethane', qchem='nitromethane'),
            ImplicitSolvent(name='o-nitrotoluene', smiles='CC1=CC=CC=C1[N+]([O-])=O', aliases=['o-nitrotoluene', 'ortho-nitrotoluene'], orca='o-nitrotoluene', g09='o-NitroToluene', nwchem='ontrtolu', mopac='o-nitrotoluene', qchem='o-nitrotoluene'),
            ImplicitSolvent(name='n-nonane', smiles='CCCCCCCCC', aliases=['n-nonane', 'nonane'], orca='n-nonane', g09='n-Nonane', nwchem='nonane', mopac='n-nonane', qchem='nonane'),
            ImplicitSolvent(name='n-octane', smiles='CCCCCCCC', aliases=['n-octane', 'octane'], orca='n-octane', g09='n-Octane', nwchem='octane', mopac='n-octane', qchem='octane'),
            ImplicitSolvent(name='n-pentadecane', smiles='CCCCCCCCCCCCCCC', aliases=['n-pentadecane', 'pentadecane'], orca='n-pentadecane', g09='n-Pentadecane', nwchem='pentdecn', mopac='n-pentadecane', qchem='decane'),
            ImplicitSolvent(name='pentanal', smiles='CCCCC=O', aliases=['pentanal'], orca='pentanal', g09='Pentanal', nwchem='pentanal', mopac='pentanal', qchem='pentanal'),
            ImplicitSolvent(name='pentanoic acid', smiles='CCCCC(O)=O', aliases=['pentanoic acid', 'valeric acid'], orca='pentanoic acid', g09='PentanoicAcid', nwchem='pentacid', mopac='pentanoic acid', qchem='pentanoic acid'),
            ImplicitSolvent(name='pentyl ethanoate', smiles='CC(OCCCCC)=O', aliases=['pentyl ethanoate', 'pentyl acetate'], orca='pentyl ethanoate', g09='PentylEthanoate', nwchem='pentacet', mopac='pentyl acetate'),
            ImplicitSolvent(name='pentyl amine', smiles='NCCCCC', aliases=['pentyl amine', 'pentylamine', '1-aminopentane'], orca='pentylamine', g09='PentylAmine', nwchem='pentamin', mopac='pentylamine', qchem='pentane'),
            ImplicitSolvent(name='perfluorobenzene', smiles='FC1=C(F)C(F)=C(F)C(F)=C1F', aliases=['perfluorobenzene', 'pfb', 'c6f6', 'hexafluorobenzene'], orca='perfluorobenzene', g09='PerFluoroBenzene', nwchem='pfb', mopac='perfluorobenzene', qchem='benzene'),
            ImplicitSolvent(name='propanal', smiles='CCC=O', aliases=['propanal'], orca='propanal', g09='Propanal', nwchem='propanal', mopac='propanal', qchem='propanal'),
            ImplicitSolvent(name='propanoic acid', smiles='CCC(O)=O', aliases=['propanoic acid', 'propionic acid'], orca='propanoic acid', g09='PropanoicAcid', nwchem='propacid', mopac='propanoic acid', qchem='propanoic acid'),
            ImplicitSolvent(name='propanenitrile', smiles='CCC#N', aliases=['propanenitrile', 'cyanoethane', 'ethyl cyanide', 'propanonitrile'], orca='propanonitrile', g09='PropanoNitrile', nwchem='propntrl', mopac='cyanoethane', qchem='propanonitrile'),
            ImplicitSolvent(name='propyl ethanoate', smiles='CC(OCCC)=O', aliases=['propyl ethanoate', 'propyl acetate'], orca='propyl ethanoate', g09='PropylEthanoate', nwchem='propacet', mopac='propyl acetate'),
            ImplicitSolvent(name='propyl amine', smiles='NCCC', aliases=['propyl amine', 'propylamine', '1-aminopropane'], orca='propylamine', g09='PropylAmine', nwchem='propamin', mopac='propylamine', qchem='propylamine'),
            ImplicitSolvent(name='tetrachloroethene', smiles='Cl/C(Cl)=C(Cl)/Cl', aliases=['tetrachloroethene', 'perchloroethene', 'pce', 'c2cl4'], orca='tetrachloroethene', g09='TetraChloroEthene', nwchem='c2cl4', mopac='tetrachloroethene', qchem='tetrachloroethene'),
            ImplicitSolvent(name='tetrahydrothiophene-s,s-dioxide', smiles='O=S1(CCCC1)=O', aliases=['tetrahydrothiophene-s,s-dioxide', 'sulfolane'], orca='tetrahydrothiophene-s,s-dioxide', g09='TetraHydroThiophene-s,s-dioxide', nwchem='sulfolan', mopac='sulfolane', qchem='thiophene'),
            ImplicitSolvent(name='tetralin', smiles='C12=C(CCCC2)C=CC=C1', aliases=['tetralin', '1,2,3,4-tetrahydronaphthalene', 'tetrahydronaphthalene'], orca='tetralin', g09='Tetralin', nwchem='tetralin', mopac='tetralin', qchem='tetralin'),
            ImplicitSolvent(name='thiophene', smiles='C1=CC=CS1', aliases=['thiophene'], orca='thiophene', g09='Thiophene', nwchem='thiophen', mopac='thiophene', qchem='thiophene'),
            ImplicitSolvent(name='thiophenol', smiles='SC1=CC=CC=C1', aliases=['thiophenol', 'phsh', 'benzenethiol'], orca='thiophenol', g09='Thiophenol', nwchem='phsh', mopac='thiophenol', qchem='benzene'),
            ImplicitSolvent(name='tributylphosphate', smiles='O=P(OCCCC)(OCCCC)OCCCC', aliases=['tributylphopshate', 'tbp', 'tributyl phopshate'], orca='tributylphopshate', g09='TriButylPhosphate', nwchem='tbp', mopac='tbp', qchem='tributylphosphate'),
            ImplicitSolvent(name='trichloroethene', smiles='Cl/C(Cl)=C/Cl', aliases=['trichloroethene', 'tce'], orca='trichloroethene', g09='TriChloroEthene', nwchem='tce', mopac='tce', qchem='trichloroethene'),
            ImplicitSolvent(name='triethylamine', smiles='CCN(CC)CC', aliases=['triethylamine', 'et3n'], orca='triethylamine', g09='TriEthylAmine', nwchem='et3n', mopac='triethylamine', qchem='triethylamine'),
            ImplicitSolvent(name='n-undecane', smiles='CCCCCCCCCCC', aliases=['n-undecane', 'undecane'], orca='n-undecane', g09='n-Undecane', nwchem='undecane', mopac='n-undecane', qchem='decane'),
            ImplicitSolvent(name='xylene mixture', smiles='CC1=CC=C(C)C=C1', aliases=['xylene mix', 'xylene (mix)', 'xylene mixture', 'xylene (mixture)', 'xylene'], orca='xyzlene (mixture)', g09='Xylene-mixture', nwchem='xylenemx', mopac='xylene mix'),
            ImplicitSolvent(name='m-xylene', smiles='CC1=CC=CC(C)=C1', aliases=['m-xylene', 'meta-xylene', '1,3-xylene'], orca='m-xylene', g09='m-Xylene', nwchem='m-xylene', mopac='m-xylene', qchem='m-xylene'),
            ImplicitSolvent(name='o-xylene', smiles='CC1=CC=CC=C1C', aliases=['o-xylene', 'ortho-xylene', '1,2-xylene'], orca='o-xylene', g09='o-Xylene', nwchem='o-xylene', mopac='o-xylene', qchem='o-xylene'),
            ImplicitSolvent(name='p-xylene', smiles='CC1=CC=C(C)C=C1', aliases=['p-xylene', 'para-xylene', '1,4-xylene'], orca='p-xylene', g09='p-Xylene', nwchem='p-xylene', mopac='p-xylene', qchem='p-xylene'),
            ImplicitSolvent(name='2-propanol', smiles='CC(O)C', aliases=['2-propanol', 'propan-2-ol', 'isopropanol', 'isopropyl alcohol'], orca='2-propanol', g09='2-Propanol', nwchem='propnol2', mopac='2-propanol', qchem='2-propanol'),
            ImplicitSolvent(name='2-propen-1-ol', smiles='C=CCO', aliases=['2-propen-1-ol', 'allyl alcohol'], orca='2-propen-1-ol', g09='2-Propen-1-ol', nwchem='propenol', mopac='2-propen-1-ol', qchem='2-propen-1-ol'),
            ImplicitSolvent(name='e-2-pentene', smiles='C/C=C/CC', aliases=['e-2-pentene', 'e-pent-2-ene'], orca='e-2-pentene', g09='e-2-Pentene', nwchem='e2penten', mopac='e-2-pentene', qchem='E-2-pentene'),
            ImplicitSolvent(name='3-methylpyridine', smiles='CC1=CC=CN=C1', aliases=['3-methylpyridine', '3-picoline'], orca='3-methylpyridine', g09='3-MethylPyridine', nwchem='mepyrid3', mopac='3-methylpyridine', qchem='3-methylpyridine'),
            ImplicitSolvent(name='3-pentanone', smiles='CCC(CC)=O', aliases=['3-pentanone', 'pentan-3-one'], orca='3-pentanone', g09='3-Pentanone', nwchem='pentnon3', mopac='3-pentanone', qchem='3-pentanone'),
            ImplicitSolvent(name='4-heptanone', smiles='CCCC(CCC)=O', aliases=['4-heptanone', 'heptan-4-one'], orca='4-heptanone', g09='4-Heptanone', nwchem='heptnon4', mopac='4-heptanone', qchem='4-heptanone'),
            ImplicitSolvent(name='4-methyl-2-pentanone', smiles='CC(CC(C)C)=O', aliases=['4-methyl-2-pentanone', 'methyl isobutyl ketone'], orca='4-methyl-2-pentanone', g09='4-Methyl-2-Pentanone', nwchem='mibk', mopac='mibk', qchem='2-pentanone'),
            ImplicitSolvent(name='4=methylpyridine', smiles='CC1=CC=NC=C1', aliases=['4-methylpyridine', '4-picoline'], orca='4-methylpyridine', g09='4-MethylPyridine', nwchem='mepyrid4', mopac='4-methylpyridine', qchem='4-methylpyridine'),
            ImplicitSolvent(name='5-nonanone', smiles='CCCCC(CCCC)=O', aliases=['5-nonanone', 'nonan-5-one'], orca='5-nonanone', g09='5-Nonanone', nwchem='nonanone', mopac='5-nonanone', qchem='5-nonanone'),
            ImplicitSolvent(name='benzyl alcohol', smiles='OCC1=CC=CC=C1', aliases=['benzyl alcohol', 'phenylmethanol', 'bnoh'], orca='benzyl alcohol', g09='BenzylAlcohol', nwchem='benzalcl', mopac='benzyl alcohol', qchem='benzyl alcohol'),
            ImplicitSolvent(name='butanoic acid', smiles='CCCC(O)=O', aliases=['butanoic acid', 'butyric acid'], orca='butanoic acid', g09='ButanoicAcid', nwchem='butacid', mopac='butanoic acid'),
            ImplicitSolvent(name='butanenitrile', smiles='CCCC#N', aliases=['butanenitrile', 'butyronitrile', 'butanonitrile'], orca='butanonitrile', g09='ButanoNitrile', nwchem='butantrl', mopac='butanenitrile', qchem='butanonitrile'),
            ImplicitSolvent(name='butyl ethanoate', smiles='CC(OCCCC)=O', aliases=['butyl ethanoate', 'butyl acetate'], orca='butyl ethanoate', g09='ButylEthanoate', nwchem='butile', mopac='butyl acetate'),
            ImplicitSolvent(name='butylamine', smiles='NCCCC', aliases=['butylamine', 'butan-1-amine'], orca='butylamine', g09='ButylAmine', nwchem='nba', mopac='butylamine', qchem='butylamine'),
            ImplicitSolvent(name='n-butylbenzene', smiles='CCCCC1=CC=CC=C1', aliases=['n-butylbenzene', 'butylbenzene', 'phenylbutane'], orca='n-butylbenzene', g09='n-ButylBenzene', nwchem='nbutbenz', mopac='n-butylbenzene', qchem='benzene'),
            ImplicitSolvent(name='sec-butylbenzene', smiles='CCC(C1=CC=CC=C1)C', aliases=['sec-butylbenzene', 's-butylbenzene'], orca='sec-butylbenzene', g09='sec-ButylBenzene', nwchem='sbutbenz', mopac='s-butylbenzene', qchem='benzene'),
            ImplicitSolvent(name='tert-butylbenzene', smiles='CC(C1=CC=CC=C1)(C)C', aliases=['tert-butylbenzene', 't-butylbenzene'], orca='tert-butylbenzene', g09='tert-ButylBenzene', nwchem='tbutbenz', mopac='t-butylbenzene', qchem='benzene'),
            ImplicitSolvent(name='o-chlorotoluene', smiles='CC1=CC=CC=C1Cl', aliases=['o-chlorotoluene', 'ortho-chlorotoluene', '2-chlorotoluene'], orca='o-chlorotoluene', g09='o-ChloroToluene', nwchem='ocltolue', mopac='o-chlorotoluene', qchem='chlorotoluene'),
            ImplicitSolvent(name='m-cresol', smiles='CC1=CC(O)=CC=C1', aliases=['m-cresol', 'meta-cresol', '3-methylphenol'], orca='m-cresol', g09='m-Cresol', nwchem='m-cresol', mopac='m-cresol', qchem='m-cresol'),
            ImplicitSolvent(name='o-cresol', smiles='CC1=CC=CC=C1O', aliases=['o-cresol', 'ortho-cresol', '2-methylphenol'], orca='o-cresol', g09='o-Cresol', nwchem='o-cresol', mopac='o-cresol', qchem='o-cresol'),
            ImplicitSolvent(name='cyclohexanone', smiles='O=C1CCCCC1', aliases=['cyclohexanone'], orca='cyclohexanone', g09='CycloHexanone', nwchem='cychexon', mopac='cyclohexanone', qchem='cyclohexanone'),
            ImplicitSolvent(name='isoquinoline', smiles='C12=C(C=NC=C2)C=CC=C1', aliases=['isoquinoline'], g09='IsoQuinoline', mopac='isoquinoline'),
            ImplicitSolvent(name='quinoline', smiles='C12=CC=CC=C1N=CC=C2', aliases=['quinoline'], g09='Quinoline', mopac='quinoline'),
            ImplicitSolvent(name='argon', smiles='[Ar]', aliases=['argon'], g09='Argon', mopac='argon'),
            ImplicitSolvent(name='krypton', smiles='[Kr]', aliases=['krypton'], g09='Krypton', mopac='krypton'),
            ImplicitSolvent(name='xenon', smiles='[Xe]', aliases=['xenon'], g09='Xenon', mopac='xenon')]


# Dielectric constants from Gaussian solvent list. Thanks to Joseph Silcock
# for PAINSTAKINGLY extracting these
_solvents_and_dielectrics = {'acetic acid': 6.25,
                             'acetone': 20.49,
                             'acetonitrile': 35.69,
                             'benzene': 2.27,
                             '1-butanol': 17.33,
                             '2-butanone': 18.25,
                             'carbon tetrachloride': 2.23,
                             'chlorobenzene': 5.70,
                             'chloroform': 4.71,
                             'cyclohexane': 2.02,
                             '1,2-dichlorobenzene': 9.99,
                             'dichloromethane': 8.93,
                             'n,n-dimethylacetamide': 37.78,
                             'n,n-dimethylformamide': 37.22,
                             '1,4-dioxane': 2.21,
                             'ether': 4.24,
                             'ethyl acetate': 5.99,
                             'tce': 3.42,
                             'ethyl alcohol': 24.85,
                             'heptane': 1.91,
                             'hexane': 1.88,
                             'pentane': 1.84,
                             '1-propanol': 20.52,
                             'pyridine': 12.98,
                             'tetrahydrofuran': 7.43,
                             'toluene': 2.37,
                             'water': 78.36,
                             'cs2': 2.61,
                             'dmso': 46.82,
                             'methanol': 32.61,
                             '2-butanol': 15.94,
                             'acetophenone': 17.44,
                             'aniline': 6.89,
                             'anisole': 4.22,
                             'benzaldehyde': 18.22,
                             'benzonitrile': 25.59,
                             'benzyl chloride': 6.72,
                             'isobutyl bromide': 7.78,
                             'bromobenzene': 5.40,
                             'bromoethane': 9.01,
                             'bromoform': 4.25,
                             'bromooctane': 5.02,
                             'bromopentane': 6.27,
                             'butanal': 13.45,
                             '1,1,1-trichloroethane': 7.08,
                             'cyclopentane': 1.96,
                             '1,1,2-trichloroethane': 7.19,
                             'cyclopentanol': 16.99,
                             '1,2,4-trimethylbenzene': 2.37,
                             'cyclopentanone': 13.58,
                             '1,2-dibromoethane': 4.93,
                             '1,2-dichloroethane': 10.13,
                             'cis-decalin': 2.21,
                             'trans-decalin': 2.18,
                             'decalin': 2.20,
                             '1,2-ethanediol': 40.25,
                             'decane': 1.98,
                             'dibromomethane': 7.23,
                             'dibutylether': 3.05,
                             'z-1,2-dichloroethene': 9.20,
                             'e-1,2-dichloroethene': 2.14,
                             '1-bromopropane': 8.05,
                             '2-bromopropane': 9.36,
                             '1-chlorohexane': 5.95,
                             '1-ChloroPentane': 6.50,
                             '1-chloropropane': 8.35,
                             'diethylamine': 3.58,
                             'decanol': 7.53,
                             'diiodomethane': 5.32,
                             '1-fluorooctane': 3.89,
                             'heptanol': 11.32,
                             'cisdmchx': 2.06,
                             'diethyl sulfide': 5.73,
                             'diisopropyl ether': 3.38,
                             'hexanol': 12.51,
                             'hexene': 2.07,
                             'hexyne': 2.62,
                             'iodobutane': 6.17,
                             '1-iodohexadecane': 3.53,
                             'diphenylether': 3.73,
                             '1-iodopentane': 5.70,
                             '1-iodopropane': 6.96,
                             'dipropylamine': 2.91,
                             'dodecane': 2.01,
                             '1-nitropropane': 23.73,
                             'ethanethiol': 6.67,
                             'nonanol': 8.60,
                             'octanol': 9.86,
                             'pentanol': 15.13,
                             'pentene': 1.99,
                             'ethylbenzene': 2.43,
                             'tbp': 8.18,
                             '2,2,2-trifluoroethanol': 26.73,
                             'fluorobenzene': 5.42,
                             '2,2,4-trimethylpentane': 1.94,
                             'formamide': 108.94,
                             '2,4-dimethylpentane': 1.89,
                             '2,4-dimethylpyridine': 9.41,
                             '2,6-dimethylpyridine': 7.17,
                             'hexadecane': 2.04,
                             'dimethyl disulfide': 9.60,
                             'ethyl methanoate': 8.33,
                             'phentole': 4.18,
                             'formic acid': 51.1,
                             'hexanoic acid': 2.6,
                             '2-chlorobutane': 8.39,
                             '2-heptanone': 11.66,
                             '2-hexanone': 14.14,
                             '2-methoxyethanol': 17.20,
                             'isobutanol': 16.78,
                             'tertbutanol': 12.47,
                             '2-methylpentane': 1.89,
                             '2-methylpyridine': 9.95,
                             '2-nitropropane': 25.65,
                             '2-octanone': 9.47,
                             '2-pentanone': 15.20,
                             'iodobenzene': 4.55,
                             'iodoethane': 7.62,
                             'iodomethane': 6.87,
                             'isopropylbenzene': 2.37,
                             'p-cymene': 2.23,
                             'mesitylene': 2.27,
                             'methyl benzoate': 6.74,
                             'methyl butanoate': 5.56,
                             'methyl acetate': 6.86,
                             'methyl formate': 8.84,
                             'methyl propanoate': 6.08,
                             'n-methylaniline': 5.96,
                             'methylcyclohexane': 2.02,
                             'nmfmixtr': 181.56,
                             'nitrobenzene': 34.81,
                             'nitroethane': 28.29,
                             'nitromethane': 36.56,
                             'o-nitrotoluene': 25.67,
                             'n-nonane': 1.96,
                             'n-octane': 1.94,
                             'n-pentadecane': 2.03,
                             'pentanal': 10.00,
                             'pentanoic acid': 2.69,
                             'pentyl acetate': 4.73,
                             'pentylamine': 4.20,
                             'perfluorobenzene': 2.03,
                             'propanal': 18.50,
                             'propanoic acid': 3.44,
                             'cyanoethane': 29.32,
                             'propyl acetate': 5.52,
                             'propylamine': 4.99,
                             'tetrachloroethene': 2.27,
                             'sulfolane': 43.96,
                             'tetralin': 2.77,
                             'thiophene': 2.73,
                             'thiophenol': 4.27,
                             'triethylamine': 2.38,
                             'n-undecane': 1.99,
                             'xylene mix': 3.29,
                             'm-xylene': 2.35,
                             'o-xylene': 2.55,
                             'p-xylene': 2.27,
                             '2-propanol': 19.26,
                             '2-propen-1-ol': 19.01,
                             'e-2-pentene': 2.05,
                             '3-methylpyridine': 11.65,
                             '3-pentanone': 16.78,
                             '4-heptanone': 12.26,
                             'mibk': 12.88,
                             '4-methylpyridine': 11.96,
                             '5-nonanone': 10.6,
                             'benzyl alcohol': 12.46,
                             'butanoic acid': 2.99,
                             'butanenitrile': 24.29,
                             'butyl acetate': 4.99,
                             'butylamine': 4.62,
                             'n-butylbenzene': 2.36,
                             's-butylbenzene': 2.34,
                             't-butylbenzene': 2.34,
                             'o-chlorotoluene': 4.63,
                             'm-cresol': 12.44,
                             'o-cresol': 6.76,
                             'cyclohexanone': 15.62,
                             'isoquinoline': 11.00,
                             'quinoline': 9.16,
                             'argon': 1.43,
                             'krypton': 1.52,
                             'xenon': 1.70}
