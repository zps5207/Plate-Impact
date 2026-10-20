C======================================================================
C     VUEL_MATERIAL: 8-Node Hexahedral Element - TOTAL LAGRANGIAN
C     FORMULATION, branched from uel/VUEL_failure.for with Rate-Dependent
C     J2 Elastic-Plasticity and Energy-Based Ductile Damage (Stage 8).
C
C     Formulation: Total Lagrangian, St. Venant-Kirchhoff Hyperelastic
C     Strain: Green-Lagrange E = 0.5*(F^T*F - I)
C     Stress: Second Piola-Kirchhoff S = C:E (elastic), or S = (1-D)*C:Ee
C     Integration: Full 2x2x2 Gauss Quadrature
C     DOFs: 3 per node (translations)
C     Damping: Stiffness-proportional Rayleigh + Bulk viscosity
C
C     MATERIAL MODELS (selected by props(14) = MAT_MODEL):
C       MAT_MODEL <= 0.0 (default):
C         Legacy model from VUEL_failure.for: IPLAST=0 (pure elastic)
C         or IPLAST=1 (linear-hardening J2 plasticity, props 8-10),
C         with engineering strain (props 7) / Jacobian (props 11)
C         failure triggers and post-failure time degradation (props 12-13).
C       MAT_MODEL >= 1.0:
C         Rate-dependent J2 plasticity with zero hardening (HMOD=0),
C         tabular log10-interpolated yield stress and ductile fracture
C         strain, linear energy-based softening (Gf, ubar_f = 2 Gf / sigy0),
C         Gauss-point damage D scaling PK2 stress by (1-D).
C
C     VOLUME-FRACTION CONSISTENCY FOR CHARACTERISTIC LENGTH L:
C       L = (ELVOL_REF)**(1.0D0/3.0D0), where ELVOL_REF = eta * the full
C       reference element volume (all 8 Gauss points)
C       and eta = max(1 - Vf, 1.0D-6) from svars(107).
C       Justification: Fracture energy Gf [J/m^2] is defined per unit area
C       of host matrix crack. Using the effective matrix reference volume
C       guarantees mesh-objective energy dissipation consistent with the
C       Stage 7 volume-fraction correction.
C
C     ELEMENT FAILURE LATCH AND DEAD-ELEMENT SENTINEL:
C       Gauss-point damage is tracked locally at each of the 8 Gauss points.
C       Element-level damage D_max = max(D_k) is stored in svars(106)
C       and svars(156). When ALL 8 Gauss points reach D >= 1.0 (D_min >= 1),
C       the element is completely softened and svars(49) is latched to 1.0.
C       Justification: Retaining element forces while any Gauss point retains
C       capacity preserves partial load-carrying ability under non-uniform
C       deformation. Under uniform single-element loading, all Gauss points
C       soften identically, tripping any and all conditions simultaneously.
C       Once latched (svars(49)=1), rhs returns zero and dtimeStable
C       reports the dead-element sentinel 1.0D30.
C
C     STABLE TIME INCREMENT AND EMBEDDED FIBERS:
C       dtimeStable is computed from the intact matrix properties (E, nu, rho).
C       Embedded fibers (E=135 GPa, native T3D2/B31 elements) enforce their
C       own stable time increment in Abaqus/Explicit (dt_fiber ~ L_fib / c_fib).
C       The VUEL host does NOT include fiber E in its own dt because host nodes
C       only carry matrix mass and stiffness.
C
C     ENERGY ACCOUNTING:
C       - energy(KBLOCK, iElIe): Damaged internal elastic strain energy
C       - energy(KBLOCK, iElPd): Accumulated plastic dissipation (pre-onset)
C       - energy(KBLOCK, iElDmd): Accumulated damage dissipation (softening)
C       - Total dissipation = ALLPD + ALLDMD = sigma_y0*eps_f + Gf/L
C
C     Props array layout (nprops = 39):
C       props(1)  = Young's modulus E [Pa]
C       props(2)  = Poisson's ratio nu [-]
C       props(3)  = Density rho [kg/m^3]
C       props(4)  = Rayleigh damping beta [s]
C       props(5)  = Linear bulk viscosity b1 [-]
C       props(6)  = Quadratic bulk viscosity b2 [-]
C       props(7)  = Legacy EPS_FAIL [-]
C       props(8)  = Legacy SIGY0 [Pa]
C       props(9)  = Legacy HMOD [Pa]
C       props(10) = Legacy IPLAST [-]
C       props(11) = Legacy JAC_FAIL [-]
C       props(12) = Legacy DEGRADE_TIME [s]
C       props(13) = Legacy COMP_RESIDUAL_BULK_FRAC [-]
C       props(14) = MAT_MODEL: 0 = legacy, 1 = ductile damage model
C       props(15) = RATE_MODE: 0 = plastic strain rate, 1 = total strain rate
C       props(16) = GF_MAT: matrix fracture energy Gf [J/m^2]
C       props(17) = RESSTIFF: residual stiffness fraction at D=1 (default 0.0)
C       props(18) = NYTAB: points in yield table (1..5)
C       props(19) = NETAB: points in fracture strain table (1..5)
C       props(20:29) = 5 pairs (rate, sigma_y) for yield stress table
C       props(30:39) = 5 pairs (rate, eps_f) for fracture strain table
C
C     State variables (nsvars = 159):
C       svars(1:48)   = PK2 stress at 8 GPs (6 components each)
C       svars(49)     = element failure flag: 0.0 = intact, 1.0 = failed/dead
C       svars(50:105) = plastic strain state at 8 GPs (6 Ep + 1 PEEQ each)
C       svars(106)    = element damage fraction D_max in [0, 1]
C       svars(107)    = fiber volume fraction Vf
C       svars(108:155)= per-GP ductile damage state (6 vars per GP):
C                       offset = 107 + (k-1)*6:
C                       +1: PEEQ (accumulated equivalent plastic strain)
C                       +2: PEEQ at damage onset (frozen during softening)
C                       +3: D (Gauss-point damage fraction)
C                       +4: sigma_y0 at onset (frozen during softening)
C                       +5: strain rate at onset (frozen during softening)
C                       +6: status flag (0=elastic, 1=plastic, 2=softening, 3=dead)
C       svars(156)    = ELEM_D_MAX (peak GP damage)
C       svars(157)    = ELEM_D_AVG (mean GP damage)
C       svars(158)    = ELEM_STATUS (0=intact, 1=softening, 2=dead)
C       svars(159)    = ELEM_DMD_ENERGY (accumulated damage dissipation [J])
C
C======================================================================
      SUBROUTINE VUEL(nblock,rhs,amass,dtimeStable,svars,nsvars,
     1                energy,
     2                nnode,ndofel,props,nprops,jprops,njprops,
     3                coords,mcrd,u,du,v,a,
     4                jtype,jElem,
     5                time,period,dtimeCur,dtimePrev,kstep,kinc,
     6                lflags,
     7                dMassScaleFactor,
     8                predef,npredef,
     9                jdltyp, adlmag)
C
      INCLUDE 'vaba_param.inc'
C
C----------------------------------------------------------------------
C     Parameter definitions
C----------------------------------------------------------------------
      PARAMETER ( jMassCalc            = 1,
     *            jIntForceAndDtStable = 2,
     *            jExternForce         = 3)
C
      PARAMETER ( iProcedure = 1,
     *            iNlgeom    = 2,
     *            iOpCode    = 3,
     *            nFlags     = 3)
C
      PARAMETER ( iElPd  = 1,
     *            iElCd  = 2,
     *            iElIe  = 3,
     *            iElTs  = 4,
     *            iElDd  = 5,
     *            iElBv  = 6,
     *            iElDe  = 7,
     *            iElHe  = 8,
     *            iElKe  = 9,
     *            iElTh  = 10,
     *            iElDmd = 11,
     *            iElDc  = 12,
     *            nElEnergy = 12)
C
      PARAMETER ( iPredValueNew = 1,
     *            iPredValueOld = 2,
     *            nPred         = 2)
C
      PARAMETER ( iStepTime  = 1,
     *            iTotalTime = 2,
     *            nTime      = 2)
C
      INTEGER NMAXTAB
      PARAMETER ( NMAXTAB = 5 )
C
C----------------------------------------------------------------------
C     Dimension statements
C----------------------------------------------------------------------
      DIMENSION rhs(nblock,ndofel),amass(nblock,ndofel,ndofel),
     1          dtimeStable(nblock),
     2          svars(nblock,nsvars),energy(nblock,nElEnergy),
     3          props(nprops),jprops(njprops),
     4          jElem(nblock),time(nTime),lflags(nFlags),
     5          coords(nblock,nnode,mcrd),
     6          u(nblock,ndofel), du(nblock,ndofel),
     7          v(nblock,ndofel), a(nblock, ndofel),
     8          dMassScaleFactor(nblock),
     9          predef(nblock,nnode,npredef,nPred),
     *          adlmag(nblock)
C
C----------------------------------------------------------------------
C     Local variables
C----------------------------------------------------------------------
C     Material properties
      REAL*8 EMOD, ENU, DENS, BETA_RAYLEIGH
      REAL*8 ALAMBDA, AMU
C
C     Bulk viscosity parameters
      REAL*8 B1_BULK, B2_BULK
      REAL*8 EVDOT, QBULK
      REAL*8 STRESS_BULK(6)
C
C     Gauss point coordinates
      REAL*8 GP
      PARAMETER (GP = 0.577350269189626D0)
      REAL*8 XIGP(8), ETGP(8), ZEGP(8)
      REAL*8 XI, ETA, ZETA, WT
C
C     Natural coordinates for each node
      REAL*8 XI_NODE(8), ETA_NODE(8), ZETA_NODE(8)
C
C     Shape functions and derivatives
      REAL*8 SHP(4,8)
      REAL*8 DN_DXI(8), DN_DETA(8), DN_DZETA(8)
      REAL*8 DN_DX(8), DN_DY(8), DN_DZ(8)
      REAL*8 XJ(3,3), XJINV(3,3), DETJ0
C
C     Deformation gradient and strain
      REAL*8 DEFGRAD(3,3)
      REAL*8 RCGREEN(3,3)
      REAL*8 GLSTRAIN(3,3)
      REAL*8 DETF, JACOBIAN
C
C     Element matrices and vectors
      REAL*8 XLOC(3,8)
      REAL*8 ULOC(3,8), VLOC(3,8)
      REAL*8 UVEC(24), VVEC(24)
      REAL*8 BL_MAT(6,24)
      REAL*8 CMAT(6,6)
      REAL*8 STRAIN_VEC(6), STRAINRATE_VEC(6)
      REAL*8 STRESS_PK2(6)
      REAL*8 STRESS_VISC(6)
      REAL*8 STRESS_TOTAL(6)
      REAL*8 FINT(24)
      REAL*8 ELEMASS
C
C     Damping and energy variables
      REAL*8 OMEGA_MAX, XI_DAMP
      REAL*8 DAMP_DISSIP, BV_DISSIP
      REAL*8 ELVOL_GEOM, ELVOL_EFF, DVOL_GEOM, DVOL_EFF, ELVOL_REF
      REAL*8 ELKE, ELIE
      REAL*8 CWAVE, CHARLEN, DTELEM
C
C     Loop indices and utilities
      INTEGER KBLOCK, IGAUSS, I, J, K, II, JJ
      INTEGER IDOF, JDOF, INODE, JNODE
      REAL*8 FACTOR
      REAL*8 SMALL
      PARAMETER (SMALL = 1.0D-30)
C
C     Legacy failure and plasticity variables
      REAL*8 EPS_FAIL
      REAL*8 STRETCH1, STRETCH2, STRETCH3
      REAL*8 ENG1, ENG2, ENG3, MAXABS_ENG
      REAL*8 ELEM_MAXABS_ENG
      LOGICAL ELEM_ALREADY_FAILED
      REAL*8 SIGY0, HMOD, IPLAST
      REAL*8 JAC_FAIL, ELEM_MIN_DETF
      REAL*8 EP_VEC(6), PEEQ_OLD
      REAL*8 EE_TRIAL_VEC(6), S_TRIAL_VEC(6), EE_NEW_VEC(6)
      REAL*8 DEP_VEC(6), SDEV(6)
      REAL*8 P_HYDRO, SIGMA_TRIAL, SIGY_OLD, SIGY_NEW, DGAMMA
      REAL*8 PLASTIC_DISSIP, DAMAGE_DISSIP
      INTEGER IGPBASE, IGP_EXTRA
C
C     Legacy Stage 5 post-failure degradation
      REAL*8 DEGRADE_TIME, COMP_RESIDUAL_FRAC
      REAL*8 FIBER_VOL_FRAC, ETA_VF_RAW, ETA_VF
      REAL*8 DAMAGE, DAMAGE_OLD, STRESS_SCALE
      REAL*8 BULK_MODULUS, VOL_ELASTIC_STRAIN, P_RESIDUAL
      REAL*8 STRESS_RESIDUAL(6)
      LOGICAL CONSTITUTIVE_ACTIVE
C
C     New Stage 8 ductile damage material variables
      REAL*8 MAT_MODEL, RATE_MODE, GF_MAT, RESSTIFF
      INTEGER NYTAB, NETAB
      REAL*8 RATE_TAB_Y(NMAXTAB), VAL_TAB_Y(NMAXTAB)
      REAL*8 RATE_TAB_F(NMAXTAB), VAL_TAB_F(NMAXTAB)
      REAL*8 CUR_RATE, SIGY_CUR, EPSF_CUR, PL_RATE
      REAL*8 TR_EDOT, EDOT_DEV(6), EDOT_EQ
      REAL*8 PEEQ_ONSET_GP, D_GP, SIGY0_ONSET_GP
      REAL*8 RATE_ONSET_GP, STATUS_GP
      REAL*8 D_OLD_GP, UBAR_F, UBAR, D_TRIAL, STRESS_SCALE_GP, DELTA_D
      REAL*8 ELEM_D_MAX, ELEM_D_MIN, ELEM_D_SUM, ELEM_D_AVG
      REAL*8 CPI_NEW(6), S_UND(6), PSI_EL, QNEW_GP, D_MID
      INTEGER IERR_H
C
C     Debug output control
      INTEGER NCALLS
      DATA NCALLS / 0 /
      SAVE NCALLS
C
C----------------------------------------------------------------------
C     Initialize natural coordinates for nodes (Abaqus C3D8 convention)
C----------------------------------------------------------------------
      DATA XI_NODE   / -1.0D0, -1.0D0,  1.0D0,  1.0D0,
     *                 -1.0D0, -1.0D0,  1.0D0,  1.0D0 /
      DATA ETA_NODE  / -1.0D0,  1.0D0,  1.0D0, -1.0D0,
     *                 -1.0D0,  1.0D0,  1.0D0, -1.0D0 /
      DATA ZETA_NODE /  1.0D0,  1.0D0,  1.0D0,  1.0D0,
     *                 -1.0D0, -1.0D0, -1.0D0, -1.0D0 /
C
C----------------------------------------------------------------------
C     Initialize Gauss point coordinates (2x2x2)
C----------------------------------------------------------------------
      DATA XIGP  / -GP,  GP,  GP, -GP, -GP,  GP,  GP, -GP /
      DATA ETGP  / -GP, -GP,  GP,  GP, -GP, -GP,  GP,  GP /
      DATA ZEGP  / -GP, -GP, -GP, -GP,  GP,  GP,  GP,  GP /
C
C----------------------------------------------------------------------
C     Extract material properties
C----------------------------------------------------------------------
      EMOD = props(1)
      ENU  = props(2)
      DENS = props(3)
      BETA_RAYLEIGH = props(4)
      B1_BULK = props(5)
      B2_BULK = props(6)
      EPS_FAIL = props(7)
      SIGY0 = props(8)
      HMOD = props(9)
      IPLAST = props(10)
      JAC_FAIL = props(11)
      DEGRADE_TIME = 0.0D0
      COMP_RESIDUAL_FRAC = 0.0D0
      IF (nprops .GE. 12) DEGRADE_TIME = DMAX1(props(12), 0.0D0)
      IF (nprops .GE. 13) THEN
        COMP_RESIDUAL_FRAC = DMAX1(0.0D0, DMIN1(props(13), 1.0D0))
      END IF
C
C     Stage 8 ductile damage properties
      MAT_MODEL = 0.0D0
      RATE_MODE = 0.0D0
      GF_MAT = 1460.0D0
      RESSTIFF = 0.0D0
      NYTAB = 1
      NETAB = 1
      DO I = 1, NMAXTAB
        RATE_TAB_Y(I) = 0.0D0
        VAL_TAB_Y(I)  = 0.0D0
        RATE_TAB_F(I) = 0.0D0
        VAL_TAB_F(I)  = 0.0D0
      END DO
C
      IF (nprops .GE. 14) MAT_MODEL = props(14)
      IF (MAT_MODEL .GT. 0.5D0) THEN
        IF (nprops .GE. 15) RATE_MODE = props(15)
        IF (nprops .GE. 16) GF_MAT    = DMAX1(props(16), 0.0D0)
        IF (nprops .GE. 17) THEN
          RESSTIFF = DMAX1(0.0D0, DMIN1(props(17), 1.0D0))
        END IF
        IF (nprops .GE. 18) THEN
          NYTAB = MIN0(NMAXTAB, MAX0(1, INT(props(18))))
        END IF
        IF (nprops .GE. 19) THEN
          NETAB = MIN0(NMAXTAB, MAX0(1, INT(props(19))))
        END IF
C       Extract yield table pairs
        DO I = 1, NYTAB
          IF (nprops .GE. (19 + 2*I)) THEN
            RATE_TAB_Y(I) = props(19 + 2*(I-1) + 1)
            VAL_TAB_Y(I)  = props(19 + 2*(I-1) + 2)
          END IF
        END DO
C       Extract fracture strain table pairs
        DO I = 1, NETAB
          IF (nprops .GE. (29 + 2*I)) THEN
            RATE_TAB_F(I) = props(29 + 2*(I-1) + 1)
            VAL_TAB_F(I)  = props(29 + 2*(I-1) + 2)
          END IF
        END DO
      END IF
C
C     Lame parameters
      ALAMBDA = EMOD * ENU / ((1.0D0 + ENU) * (1.0D0 - 2.0D0 * ENU))
      AMU     = EMOD / (2.0D0 * (1.0D0 + ENU))
      BULK_MODULUS = ALAMBDA + 2.0D0*AMU/3.0D0
C
C----------------------------------------------------------------------
C     Build 3D isotropic elasticity matrix (Total Lagrangian PK2 vs GL)
C----------------------------------------------------------------------
      DO I = 1, 6
        DO J = 1, 6
          CMAT(I,J) = 0.0D0
        END DO
      END DO
C
      CMAT(1,1) = ALAMBDA + 2.0D0 * AMU
      CMAT(2,2) = ALAMBDA + 2.0D0 * AMU
      CMAT(3,3) = ALAMBDA + 2.0D0 * AMU
      CMAT(4,4) = AMU
      CMAT(5,5) = AMU
      CMAT(6,6) = AMU
C
      CMAT(1,2) = ALAMBDA
      CMAT(1,3) = ALAMBDA
      CMAT(2,1) = ALAMBDA
      CMAT(2,3) = ALAMBDA
      CMAT(3,1) = ALAMBDA
      CMAT(3,2) = ALAMBDA
C
C======================================================================
C     MAIN LOOP OVER ELEMENT BLOCKS
C======================================================================
      NCALLS = NCALLS + 1
C
      IF (NCALLS .EQ. 1) THEN
        WRITE(*,*) '=== VUEL_MATERIAL (STAGE 8): FIRST CALL ==='
        WRITE(*,*) 'E =', EMOD, ' nu =', ENU, ' rho =', DENS
        WRITE(*,*) 'MAT_MODEL =', MAT_MODEL, ' RATE_MODE =', RATE_MODE
        WRITE(*,*) 'GF_MAT =', GF_MAT, ' RESSTIFF =', RESSTIFF
        WRITE(*,*) 'NYTAB =', NYTAB, ' NETAB =', NETAB
        IF (MAT_MODEL .GT. 0.5D0) THEN
          WRITE(*,*) 'Yield table (rate, sigy):',
     *               RATE_TAB_Y(1), VAL_TAB_Y(1)
          WRITE(*,*) 'Fracture table (rate, epsf):',
     *               RATE_TAB_F(1), VAL_TAB_F(1)
        END IF
      END IF
C
      DO KBLOCK = 1, nblock
C       Per-element matrix volume fraction from svars(107)
        FIBER_VOL_FRAC = 0.0D0
        IF (nsvars .GE. 107) FIBER_VOL_FRAC = svars(KBLOCK,107)
        ETA_VF_RAW = 1.0D0 - FIBER_VOL_FRAC
        ETA_VF = DMAX1(ETA_VF_RAW, 1.0D-6)
C
C----------------------------------------------------------------------
C       Extract REFERENCE nodal coordinates (undeformed)
C----------------------------------------------------------------------
        DO INODE = 1, 8
          DO I = 1, 3
            XLOC(I, INODE) = coords(KBLOCK, INODE, I)
          END DO
        END DO
C
C       Extract nodal displacements and velocities
        DO INODE = 1, 8
          DO I = 1, 3
            IDOF = (INODE - 1) * 3 + I
            ULOC(I, INODE) = u(KBLOCK, IDOF)
            VLOC(I, INODE) = v(KBLOCK, IDOF)
            UVEC(IDOF) = ULOC(I, INODE)
            VVEC(IDOF) = VLOC(I, INODE)
          END DO
        END DO
C
C======================================================================
C       OPERATION CODE: MASS MATRIX CALCULATION
C======================================================================
        IF (lflags(iOpCode) .EQ. jMassCalc) THEN
C
          DO I = 1, ndofel
            DO J = 1, ndofel
              amass(KBLOCK, I, J) = 0.0D0
            END DO
          END DO
C
          ELVOL_GEOM = 0.0D0
C
          DO IGAUSS = 1, 8
            XI   = XIGP(IGAUSS)
            ETA  = ETGP(IGAUSS)
            ZETA = ZEGP(IGAUSS)
            WT   = 1.0D0
C
            CALL SHAPE8H_TL(XI, ETA, ZETA, XLOC,
     *                      XI_NODE, ETA_NODE, ZETA_NODE,
     *                      SHP, DN_DX, DN_DY, DN_DZ,
     *                      XJ, XJINV, DETJ0)
C
            DVOL_GEOM = DETJ0 * WT
            ELVOL_GEOM = ELVOL_GEOM + DVOL_GEOM
          END DO
C
          ELVOL_EFF = ETA_VF * ELVOL_GEOM
          ELEMASS = DENS * ELVOL_EFF
C
          DO INODE = 1, 8
            DO I = 1, 3
              IDOF = (INODE - 1) * 3 + I
              amass(KBLOCK, IDOF, IDOF) = ELEMASS / 8.0D0
            END DO
          END DO
C
        END IF
C
C======================================================================
C       OPERATION CODE: INTERNAL FORCE AND STABLE TIME INCREMENT
C======================================================================
        IF (lflags(iOpCode) .EQ. jIntForceAndDtStable) THEN
C
          DO I = 1, 24
            FINT(I) = 0.0D0
          END DO
          ELIE = 0.0D0
          ELKE = 0.0D0
          ELVOL_GEOM = 0.0D0
          ELVOL_EFF = 0.0D0
          DAMP_DISSIP = 0.0D0
          BV_DISSIP = 0.0D0
          PLASTIC_DISSIP = 0.0D0
          DAMAGE_DISSIP = 0.0D0
C
          CWAVE = DSQRT((ALAMBDA + 2.0D0 * AMU) / DENS)
          ELEM_ALREADY_FAILED = (svars(KBLOCK,49) .GT. 0.5D0)
C
C         Handle legacy degradation vs new ductile damage
          IF (MAT_MODEL .LE. 0.5D0) THEN
            DAMAGE_OLD = 0.0D0
            DAMAGE = 0.0D0
            IF (ELEM_ALREADY_FAILED) THEN
              IF ((DEGRADE_TIME .GT. SMALL) .AND.
     *            (nsvars .GE. 106)) THEN
                DAMAGE_OLD = DMAX1(0.0D0,
     *                       DMIN1(svars(KBLOCK,106), 1.0D0))
                DAMAGE = DMIN1(1.0D0,
     *                   DAMAGE_OLD + dtimeCur/DEGRADE_TIME)
              ELSE
                DAMAGE_OLD = 1.0D0
                DAMAGE = 1.0D0
              END IF
              IF (nsvars .GE. 106) svars(KBLOCK,106) = DAMAGE
            END IF
            STRESS_SCALE = DMAX1(0.0D0, 1.0D0-DAMAGE)
            CONSTITUTIVE_ACTIVE = ((.NOT. ELEM_ALREADY_FAILED) .OR.
     *                             (STRESS_SCALE .GT. SMALL))
          ELSE
C           New model: check if element is already marked fully dead
            CONSTITUTIVE_ACTIVE = (.NOT. ELEM_ALREADY_FAILED)
            STRESS_SCALE = 1.0D0
          END IF
C
          ELEM_MAXABS_ENG = 0.0D0
          ELEM_MIN_DETF = 1.0D30
          ELEM_D_MAX = 0.0D0
          ELEM_D_MIN = 1.0D0
          ELEM_D_SUM = 0.0D0
C
C         Full reference element volume for the softening length.
C         ELVOL_EFF below is accumulated Gauss point by Gauss point, so
C         using it inside the loop gave GP k only k/8 of the volume.
          ELVOL_REF = 0.0D0
          DO IGAUSS = 1, 8
            CALL SHAPE8H_TL(XIGP(IGAUSS), ETGP(IGAUSS), ZEGP(IGAUSS),
     *                      XLOC, XI_NODE, ETA_NODE, ZETA_NODE,
     *                      SHP, DN_DX, DN_DY, DN_DZ,
     *                      XJ, XJINV, DETJ0)
            ELVOL_REF = ELVOL_REF + ETA_VF * DETJ0
          END DO
C         Loop over Gauss points
          DO IGAUSS = 1, 8
            XI   = XIGP(IGAUSS)
            ETA  = ETGP(IGAUSS)
            ZETA = ZEGP(IGAUSS)
            WT   = 1.0D0
C
            CALL SHAPE8H_TL(XI, ETA, ZETA, XLOC,
     *                      XI_NODE, ETA_NODE, ZETA_NODE,
     *                      SHP, DN_DX, DN_DY, DN_DZ,
     *                      XJ, XJINV, DETJ0)
C
            DVOL_GEOM = DETJ0 * WT
            DVOL_EFF = ETA_VF * DVOL_GEOM
            ELVOL_GEOM = ELVOL_GEOM + DVOL_GEOM
            ELVOL_EFF = ELVOL_EFF + DVOL_EFF
C
            CALL COMPUTE_DEFGRAD(ULOC, DN_DX, DN_DY, DN_DZ,
     *                           DEFGRAD, DETF)
            ELEM_MIN_DETF = DMIN1(ELEM_MIN_DETF, DETF)
C
            CALL COMPUTE_GREEN_LAGRANGE(DEFGRAD, GLSTRAIN, STRAIN_VEC)
C
            STRETCH1 = DSQRT(DMAX1(2.0D0*STRAIN_VEC(1) + 1.0D0, 0.0D0))
            STRETCH2 = DSQRT(DMAX1(2.0D0*STRAIN_VEC(2) + 1.0D0, 0.0D0))
            STRETCH3 = DSQRT(DMAX1(2.0D0*STRAIN_VEC(3) + 1.0D0, 0.0D0))
            ENG1 = STRETCH1 - 1.0D0
            ENG2 = STRETCH2 - 1.0D0
            ENG3 = STRETCH3 - 1.0D0
            MAXABS_ENG = DMAX1(DABS(ENG1), DABS(ENG2), DABS(ENG3))
            ELEM_MAXABS_ENG = DMAX1(ELEM_MAXABS_ENG, MAXABS_ENG)
C
            CALL COMPUTE_STRAINRATE_TL(VLOC, DN_DX, DN_DY, DN_DZ,
     *                                  DEFGRAD, STRAINRATE_VEC)
C
            CALL BUILD_BL_MATRIX(DN_DX, DN_DY, DN_DZ, DEFGRAD, BL_MAT)
C
            IGPBASE = 49 + (IGAUSS-1)*7
            IGP_EXTRA = 107 + (IGAUSS-1)*6
            DO I = 1, 6
              EP_VEC(I) = svars(KBLOCK, IGPBASE+I)
            END DO
            PEEQ_OLD = svars(KBLOCK, IGPBASE+7)
            DGAMMA = 0.0D0
C
            IF (.NOT. CONSTITUTIVE_ACTIVE) THEN
              DO I = 1, 6
                STRESS_PK2(I) = 0.0D0
              END DO
              D_GP = 1.0D0
              ELEM_D_MAX = 1.0D0
              ELEM_D_MIN = 1.0D0
              ELEM_D_SUM = ELEM_D_SUM + 1.0D0
C
            ELSE IF (MAT_MODEL .LE. 0.5D0) THEN
C             --------------------------------------------------------
C             LEGACY CONSTITUTIVE PATH (VUEL_failure.for)
C             --------------------------------------------------------
              SIGY_OLD = SIGY0 + HMOD*PEEQ_OLD
              SIGY_NEW = SIGY_OLD
C
              DO I = 1, 6
                EE_TRIAL_VEC(I) = STRAIN_VEC(I) - EP_VEC(I)
              END DO
              DO I = 1, 6
                S_TRIAL_VEC(I) = 0.0D0
                DO J = 1, 6
                  S_TRIAL_VEC(I) = S_TRIAL_VEC(I) +
     *                             CMAT(I,J)*EE_TRIAL_VEC(J)
                END DO
              END DO
C
              DO I = 1, 6
                DEP_VEC(I) = 0.0D0
              END DO
C
              IF (IPLAST .GT. 0.5D0) THEN
                P_HYDRO = (S_TRIAL_VEC(1)+S_TRIAL_VEC(2)
     *                    +S_TRIAL_VEC(3)) / 3.0D0
                SDEV(1) = S_TRIAL_VEC(1) - P_HYDRO
                SDEV(2) = S_TRIAL_VEC(2) - P_HYDRO
                SDEV(3) = S_TRIAL_VEC(3) - P_HYDRO
                SDEV(4) = S_TRIAL_VEC(4)
                SDEV(5) = S_TRIAL_VEC(5)
                SDEV(6) = S_TRIAL_VEC(6)
C
                SIGMA_TRIAL = DSQRT(DMAX1(1.5D0*(
     *              SDEV(1)*SDEV(1) + SDEV(2)*SDEV(2)
     *              + SDEV(3)*SDEV(3)
     *              + 2.0D0*(SDEV(4)*SDEV(4) + SDEV(5)*SDEV(5)
     *                       + SDEV(6)*SDEV(6))), 0.0D0))
C
                IF ((SIGMA_TRIAL .GT. SIGY_OLD) .AND.
     *              ((3.0D0*AMU + HMOD) .GT. SMALL)) THEN
                  DGAMMA = (SIGMA_TRIAL - SIGY_OLD) / (3.0D0*AMU + HMOD)
                  SIGY_NEW = SIGY_OLD + HMOD*DGAMMA
                  PEEQ_OLD = PEEQ_OLD + DGAMMA
                  IF (SIGMA_TRIAL .GT. SMALL) THEN
                    FACTOR = 1.5D0 * DGAMMA / SIGMA_TRIAL
                  ELSE
                    FACTOR = 0.0D0
                  END IF
                  DEP_VEC(1) = FACTOR*SDEV(1)
                  DEP_VEC(2) = FACTOR*SDEV(2)
                  DEP_VEC(3) = FACTOR*SDEV(3)
                  DEP_VEC(4) = 2.0D0*FACTOR*SDEV(4)
                  DEP_VEC(5) = 2.0D0*FACTOR*SDEV(5)
                  DEP_VEC(6) = 2.0D0*FACTOR*SDEV(6)
                  DO I = 1, 6
                    EP_VEC(I) = EP_VEC(I) + DEP_VEC(I)
                  END DO
                END IF
              END IF
C
              DO I = 1, 6
                STRESS_PK2(I) = S_TRIAL_VEC(I)
                DO J = 1, 6
                  STRESS_PK2(I) = STRESS_PK2(I) - CMAT(I,J)*DEP_VEC(J)
                END DO
              END DO
C
              DO I = 1, 6
                svars(KBLOCK, IGPBASE+I) = EP_VEC(I)
              END DO
              svars(KBLOCK, IGPBASE+7) = PEEQ_OLD
C
            ELSE
C             --------------------------------------------------------
C             STAGE 8 DUCTILE DAMAGE CONSTITUTIVE PATH
C             --------------------------------------------------------
              PEEQ_ONSET_GP   = 0.0D0
              D_GP            = 0.0D0
              SIGY0_ONSET_GP  = 0.0D0
              RATE_ONSET_GP   = 0.0D0
              STATUS_GP       = 0.0D0
              IF (nsvars .GE. (IGP_EXTRA+6)) THEN
                PEEQ_ONSET_GP   = svars(KBLOCK, IGP_EXTRA+2)
                D_GP            = svars(KBLOCK, IGP_EXTRA+3)
                SIGY0_ONSET_GP  = svars(KBLOCK, IGP_EXTRA+4)
                RATE_ONSET_GP   = svars(KBLOCK, IGP_EXTRA+5)
                STATUS_GP       = svars(KBLOCK, IGP_EXTRA+6)
              END IF
C
C             Determine current rate
              IF (RATE_MODE .GT. 0.5D0) THEN
                TR_EDOT = STRAINRATE_VEC(1) + STRAINRATE_VEC(2)
     *                  + STRAINRATE_VEC(3)
                EDOT_DEV(1) = STRAINRATE_VEC(1) - TR_EDOT/3.0D0
                EDOT_DEV(2) = STRAINRATE_VEC(2) - TR_EDOT/3.0D0
                EDOT_DEV(3) = STRAINRATE_VEC(3) - TR_EDOT/3.0D0
                EDOT_DEV(4) = STRAINRATE_VEC(4) / 2.0D0
                EDOT_DEV(5) = STRAINRATE_VEC(5) / 2.0D0
                EDOT_DEV(6) = STRAINRATE_VEC(6) / 2.0D0
                EDOT_EQ = DSQRT(DMAX1(0.0D0, (2.0D0/3.0D0)*(
     *              EDOT_DEV(1)**2 + EDOT_DEV(2)**2 + EDOT_DEV(3)**2
     *            + 2.0D0*(EDOT_DEV(4)**2 + EDOT_DEV(5)**2
     *                     + EDOT_DEV(6)**2))))
                CUR_RATE = EDOT_EQ
              ELSE
                CUR_RATE = 0.0D0
              END IF
C
              CALL INTERP_RATE_TABLE_VUEL(CUR_RATE, NYTAB,
     *                                    RATE_TAB_Y, VAL_TAB_Y,
     *                                    SIGY_CUR)
C
C             Finite-strain J2 (Stage 8b): Hencky elasticity with a
C             log-strain radial return on Kirchhoff stress. Yield is
C             tested against SIGY_CUR*J, i.e. SIGY_CUR on Cauchy stress,
C             as native Abaqus does. EP_VEC carries Cp^-1 - I.
              CALL HENCKY_RETURN(DEFGRAD, EP_VEC, AMU, ALAMBDA,
     *                           SIGY_CUR, S_UND, CPI_NEW, DGAMMA,
     *                           PSI_EL, QNEW_GP, IERR_H)
              IF ((DGAMMA .GT. 0.0D0) .AND.
     *            (RATE_MODE .LT. 0.5D0) .AND.
     *            (dtimeCur .GT. 1.0D-12)) THEN
                PL_RATE = DGAMMA / dtimeCur
                CALL INTERP_RATE_TABLE_VUEL(PL_RATE, NYTAB,
     *                                      RATE_TAB_Y, VAL_TAB_Y,
     *                                      SIGY_CUR)
                CALL HENCKY_RETURN(DEFGRAD, EP_VEC, AMU, ALAMBDA,
     *                             SIGY_CUR, S_UND, CPI_NEW, DGAMMA,
     *                             PSI_EL, QNEW_GP, IERR_H)
                CUR_RATE = PL_RATE
              END IF
              IF (DGAMMA .GT. 0.0D0) THEN
                PEEQ_OLD = PEEQ_OLD + DGAMMA
                IF (STATUS_GP .LT. 0.5D0) STATUS_GP = 1.0D0
              END IF
              DO I = 1, 6
                EP_VEC(I) = CPI_NEW(I)
                STRESS_PK2(I) = S_UND(I)
              END DO
C
C             Damage onset check
              CALL INTERP_RATE_TABLE_VUEL(CUR_RATE, NETAB,
     *                                    RATE_TAB_F, VAL_TAB_F,
     *                                    EPSF_CUR)
              IF (STATUS_GP .LT. 1.5D0) THEN
                IF (PEEQ_OLD .GE. EPSF_CUR) THEN
                  STATUS_GP = 2.0D0
                  PEEQ_ONSET_GP = EPSF_CUR
                  SIGY0_ONSET_GP = SIGY_CUR
                  RATE_ONSET_GP = CUR_RATE
                END IF
              END IF
C
C             Damage evolution (linear softening)
              D_OLD_GP = D_GP
              IF ((STATUS_GP .GE. 1.5D0) .AND.
     *            (STATUS_GP .LT. 2.5D0)) THEN
                CHARLEN = ELVOL_REF ** (1.0D0 / 3.0D0)
                UBAR_F = 2.0D0 * GF_MAT / DMAX1(SIGY0_ONSET_GP, 1.0D0)
                UBAR = CHARLEN * (PEEQ_OLD - PEEQ_ONSET_GP)
                D_TRIAL = UBAR / UBAR_F
                D_GP = DMIN1(1.0D0, DMAX1(D_GP, D_TRIAL))
                IF (D_GP .GE. 1.0D0) THEN
                  D_GP = 1.0D0
                  STATUS_GP = 3.0D0
                END IF
              ELSE IF (STATUS_GP .GE. 2.5D0) THEN
                D_GP = 1.0D0
              END IF
C
C             Scale PK2 stress by (1 - D)
              IF (D_GP .LT. 1.0D0) THEN
                STRESS_SCALE_GP = DMAX1(RESSTIFF, 1.0D0 - D_GP)
              ELSE
                STRESS_SCALE_GP = RESSTIFF
              END IF
C
              DO I = 1, 6
                STRESS_PK2(I) = STRESS_SCALE_GP * STRESS_PK2(I)
              END DO
C
C             Dissipation tracking. Power = (1-D)(dPsi + q dgam), so
C             plastic dissipation carries (1-D) and the elastic energy
C             released as D grows (Psi dD) is the damage dissipation,
C             as in native Abaqus ALLDMD. The Gf/L term is already part
C             of the (1-D)-weighted plastic dissipation.
              D_MID = 0.5D0 * (D_OLD_GP + D_GP)
              PLASTIC_DISSIP = PLASTIC_DISSIP
     *          + (1.0D0 - D_MID) * QNEW_GP * DGAMMA * DVOL_EFF
              DAMAGE_DISSIP = DAMAGE_DISSIP
     *          + PSI_EL * (D_GP - D_OLD_GP) * DVOL_EFF
C
C             Track GP damage for element summary
              ELEM_D_MAX = DMAX1(ELEM_D_MAX, D_GP)
              ELEM_D_MIN = DMIN1(ELEM_D_MIN, D_GP)
              ELEM_D_SUM = ELEM_D_SUM + D_GP
C
C             Write updated state to svars
              DO I = 1, 6
                svars(KBLOCK, IGPBASE+I) = EP_VEC(I)
              END DO
              svars(KBLOCK, IGPBASE+7) = PEEQ_OLD
              IF (nsvars .GE. (IGP_EXTRA+6)) THEN
                svars(KBLOCK, IGP_EXTRA+1) = PEEQ_OLD
                svars(KBLOCK, IGP_EXTRA+2) = PEEQ_ONSET_GP
                svars(KBLOCK, IGP_EXTRA+3) = D_GP
                svars(KBLOCK, IGP_EXTRA+4) = SIGY0_ONSET_GP
                svars(KBLOCK, IGP_EXTRA+5) = RATE_ONSET_GP
                svars(KBLOCK, IGP_EXTRA+6) = STATUS_GP
              END IF
            END IF
C
            DO I = 1, 6
              EE_NEW_VEC(I) = STRAIN_VEC(I) - EP_VEC(I)
            END DO
C
C           Viscous and bulk damping stress
            DO I = 1, 6
              STRESS_VISC(I) = 0.0D0
              DO J = 1, 6
                STRESS_VISC(I) = STRESS_VISC(I) + BETA_RAYLEIGH
     *                           * CMAT(I,J) * STRAINRATE_VEC(J)
              END DO
            END DO
C
            EVDOT = STRAINRATE_VEC(1) + STRAINRATE_VEC(2)
     *            + STRAINRATE_VEC(3)
            DO I = 1, 6
              STRESS_BULK(I) = 0.0D0
            END DO
            QBULK = 0.0D0
            IF (EVDOT .LT. 0.0D0) THEN
              CHARLEN = DVOL_GEOM ** (1.0D0 / 3.0D0)
              QBULK = DENS * CHARLEN * (
     *                B1_BULK * CWAVE * DABS(EVDOT) +
     *                B2_BULK * CHARLEN * EVDOT * EVDOT )
              STRESS_BULK(1) = -QBULK
              STRESS_BULK(2) = -QBULK
              STRESS_BULK(3) = -QBULK
            END IF
C
C           Total stress assembly
            IF (MAT_MODEL .LE. 0.5D0) THEN
              VOL_ELASTIC_STRAIN = EE_NEW_VEC(1) + EE_NEW_VEC(2)
     *                           + EE_NEW_VEC(3)
              DO I = 1, 6
                STRESS_RESIDUAL(I) = 0.0D0
              END DO
              P_RESIDUAL = 0.0D0
              IF (ELEM_ALREADY_FAILED .AND.
     *            (COMP_RESIDUAL_FRAC .GT. 0.0D0) .AND.
     *            (VOL_ELASTIC_STRAIN .LT. 0.0D0)) THEN
                P_RESIDUAL = COMP_RESIDUAL_FRAC * BULK_MODULUS
     *                       * VOL_ELASTIC_STRAIN
                STRESS_RESIDUAL(1) = P_RESIDUAL
                STRESS_RESIDUAL(2) = P_RESIDUAL
                STRESS_RESIDUAL(3) = P_RESIDUAL
              END IF
              DO I = 1, 6
                STRESS_TOTAL(I) = STRESS_SCALE *
     *            (STRESS_PK2(I) + STRESS_VISC(I) + STRESS_BULK(I))
     *            + DAMAGE * STRESS_RESIDUAL(I)
              END DO
            ELSE
              DO I = 1, 6
                STRESS_TOTAL(I) = STRESS_PK2(I) + STRESS_SCALE_GP*
     *            (STRESS_VISC(I) + STRESS_BULK(I))
              END DO
            END IF
C
            DO I = 1, 6
              svars(KBLOCK, (IGAUSS-1)*6 + I) = STRESS_TOTAL(I)
            END DO
C
C           Internal force integration
            DO I = 1, 24
              DO J = 1, 6
                IF (MAT_MODEL .LE. 0.5D0) THEN
                  FINT(I) = FINT(I) + BL_MAT(J,I) *
     *              (STRESS_SCALE*STRESS_PK2(J)
     *               + DAMAGE*STRESS_RESIDUAL(J)) * DVOL_EFF
                  FINT(I) = FINT(I) + BL_MAT(J,I) * STRESS_SCALE *
     *              (STRESS_VISC(J) + STRESS_BULK(J)) * DVOL_GEOM
                ELSE
                  FINT(I) = FINT(I) + BL_MAT(J,I) * STRESS_PK2(J)
     *                              * DVOL_EFF
                  FINT(I) = FINT(I) + BL_MAT(J,I) * STRESS_SCALE_GP *
     *              (STRESS_VISC(J) + STRESS_BULK(J)) * DVOL_GEOM
                END IF
              END DO
            END DO
C
C           Energy integration
            IF (CONSTITUTIVE_ACTIVE) THEN
              IF (MAT_MODEL .LE. 0.5D0) THEN
                DO I = 1, 6
                  ELIE = ELIE + 0.5D0 * STRESS_PK2(I)
     *                        * EE_NEW_VEC(I) * DVOL_EFF
                END DO
              ELSE
                ELIE = ELIE + (1.0D0 - D_GP) * PSI_EL * DVOL_EFF
              END IF
              IF (MAT_MODEL .LE. 0.5D0) THEN
                PLASTIC_DISSIP = PLASTIC_DISSIP + STRESS_SCALE
     *            * 0.5D0*(SIGY_OLD+SIGY_NEW)*DGAMMA*DVOL_EFF
              END IF
            END IF
            IF (MAT_MODEL .LE. 0.5D0 .AND. ELEM_ALREADY_FAILED
     *          .AND. (VOL_ELASTIC_STRAIN .LT. 0.0D0)
     *          .AND. (COMP_RESIDUAL_FRAC .GT. 0.0D0)) THEN
              ELIE = ELIE + 0.5D0*DAMAGE*COMP_RESIDUAL_FRAC
     *             * BULK_MODULUS*VOL_ELASTIC_STRAIN**2*DVOL_EFF
            END IF
C
            IF (MAT_MODEL .LE. 0.5D0) THEN
              IF (STRESS_SCALE .GT. SMALL) THEN
                DO I = 1, 6
                  DAMP_DISSIP = DAMP_DISSIP + STRESS_SCALE
     *              * STRESS_VISC(I)*STRAINRATE_VEC(I)
     *              * DVOL_GEOM * dtimeCur
                END DO
                IF (EVDOT .LT. 0.0D0) THEN
                  BV_DISSIP = BV_DISSIP + STRESS_SCALE*QBULK
     *              * DABS(EVDOT)*DVOL_GEOM*dtimeCur
                END IF
              END IF
            ELSE
              IF (STRESS_SCALE_GP .GT. SMALL) THEN
                DO I = 1, 6
                  DAMP_DISSIP = DAMP_DISSIP + STRESS_SCALE_GP
     *              * STRESS_VISC(I)*STRAINRATE_VEC(I)
     *              * DVOL_GEOM * dtimeCur
                END DO
                IF (EVDOT .LT. 0.0D0) THEN
                  BV_DISSIP = BV_DISSIP + STRESS_SCALE_GP*QBULK
     *              * DABS(EVDOT)*DVOL_GEOM*dtimeCur
                END IF
              END IF
            END IF
C
          END DO
C
C         Failure checks
          IF (MAT_MODEL .LE. 0.5D0) THEN
            IF (.NOT. ELEM_ALREADY_FAILED) THEN
              IF (ELEM_MAXABS_ENG .GE. EPS_FAIL) THEN
                svars(KBLOCK, 49) = 1.0D0
                IF (nsvars .GE. 106) svars(KBLOCK,106) = 0.0D0
              ELSE IF ((ELEM_MIN_DETF .LE. JAC_FAIL) .OR.
     *                 (ELEM_MIN_DETF .LE. 0.0D0)) THEN
                svars(KBLOCK, 49) = 1.0D0
                IF (nsvars .GE. 106) svars(KBLOCK,106) = 0.0D0
              END IF
            END IF
          ELSE
C           New Stage 8 element-level failure logic
            ELEM_D_AVG = ELEM_D_SUM / 8.0D0
            IF (nsvars .GE. 106) svars(KBLOCK, 106) = ELEM_D_MAX
            IF (nsvars .GE. 156) svars(KBLOCK, 156) = ELEM_D_MAX
            IF (nsvars .GE. 157) svars(KBLOCK, 157) = ELEM_D_AVG
            IF (nsvars .GE. 159) THEN
              svars(KBLOCK, 159) = svars(KBLOCK, 159) + DAMAGE_DISSIP
            END IF
C
            IF (.NOT. ELEM_ALREADY_FAILED) THEN
              IF (ELEM_D_MIN .GE. (1.0D0 - 1.0D-6)) THEN
                svars(KBLOCK, 49) = 1.0D0
                IF (nsvars .GE. 158) svars(KBLOCK, 158) = 2.0D0
                WRITE(*,*) '*** VUEL_MATERIAL_FAIL: elem =',
     *                     jElem(KBLOCK), ' failed at time =',
     *                     time(iTotalTime)
              ELSE IF (ELEM_D_MAX .GT. 0.0D0) THEN
                IF (nsvars .GE. 158) svars(KBLOCK, 158) = 1.0D0
              END IF
            END IF
          END IF
C
C         Assemble RHS
          DO I = 1, 24
            rhs(KBLOCK, I) = FINT(I)
          END DO
C
C         Kinetic energy
          ELEMASS = DENS * ELVOL_EFF
          DO INODE = 1, 8
            DO I = 1, 3
              ELKE = ELKE + 0.5D0 * (ELEMASS / 8.0D0)
     *                      * VLOC(I, INODE) * VLOC(I, INODE)
            END DO
          END DO
C
C         Update energy array
          energy(KBLOCK, iElIe) = ELIE
          energy(KBLOCK, iElKe) = ELKE
          energy(KBLOCK, iElDd) = energy(KBLOCK, iElDd) + DAMP_DISSIP
          energy(KBLOCK, iElBv) = energy(KBLOCK, iElBv) + BV_DISSIP
          energy(KBLOCK, iElPd) = energy(KBLOCK, iElPd) + PLASTIC_DISSIP
          IF (MAT_MODEL .GT. 0.5D0) THEN
            energy(KBLOCK, iElDmd) = energy(KBLOCK, iElDmd)
     *                             + DAMAGE_DISSIP
          END IF
C
C         Stable time increment
          IF (MAT_MODEL .LE. 0.5D0) THEN
            IF (ELEM_ALREADY_FAILED .AND.
     *          (STRESS_SCALE .LE. SMALL) .AND.
     *          (COMP_RESIDUAL_FRAC .LE. SMALL)) THEN
              dtimeStable(KBLOCK) = 1.0D30
            ELSE
              CHARLEN = ELVOL_GEOM ** (1.0D0 / 3.0D0)
              OMEGA_MAX = CWAVE / CHARLEN * 2.0D0
              XI_DAMP = BETA_RAYLEIGH * OMEGA_MAX / 2.0D0
              DTELEM = (2.0D0 / OMEGA_MAX) *
     *                 (DSQRT(1.0D0 + XI_DAMP*XI_DAMP) - XI_DAMP)
              dtimeStable(KBLOCK) = 0.8D0 * DTELEM
            END IF
          ELSE
            IF ((svars(KBLOCK, 49) .GT. 0.5D0) .AND.
     *          (RESSTIFF .LE. SMALL)) THEN
              dtimeStable(KBLOCK) = 1.0D30
            ELSE
C             Lumped full-integration brick: the pure volumetric mode
C             has omega^2 = 12 K/(rho L^2), up to sqrt(3) above the 1D
C             bar estimate 2c/L (1.6x at nu = 0.45), so the bar-based
C             increment is unstable once J oscillates (seen in 1000 /s
C             tension). Divide by sqrt(3) for the Stage 8 material.
              CHARLEN = ELVOL_GEOM ** (1.0D0 / 3.0D0)
              OMEGA_MAX = CWAVE / CHARLEN * 2.0D0 * DSQRT(3.0D0)
              XI_DAMP = BETA_RAYLEIGH * OMEGA_MAX / 2.0D0
              DTELEM = (2.0D0 / OMEGA_MAX) *
     *                 (DSQRT(1.0D0 + XI_DAMP*XI_DAMP) - XI_DAMP)
              dtimeStable(KBLOCK) = 0.8D0 * DTELEM
            END IF
          END IF
C
        END IF
C
C======================================================================
C       OPERATION CODE: EXTERNAL FORCE
C======================================================================
        IF (lflags(iOpCode) .EQ. jExternForce) THEN
        END IF
C
      END DO
C
      RETURN
      END
C
C======================================================================
C     SUBROUTINE INTERP_RATE_TABLE_VUEL
C     Log10-linear interpolation of tabular rate-dependent properties
C======================================================================
      SUBROUTINE INTERP_RATE_TABLE_VUEL(RATE, NTAB, RTAB, VALTAB, VAL)
      IMPLICIT NONE
      INTEGER NTAB, I
      REAL*8 RATE, VAL
      REAL*8 RTAB(NTAB), VALTAB(NTAB)
      REAL*8 R_VAL, R0, R1, U, LOGR, LOGR0, LOGR1
      REAL*8 R_FLOOR
      PARAMETER ( R_FLOOR = 1.0D-12 )
C
      IF (NTAB .LE. 1) THEN
        VAL = VALTAB(1)
        RETURN
      END IF
C
      R_VAL = DMAX1(RATE, R_FLOOR)
      IF (R_VAL .LE. RTAB(1)) THEN
        VAL = VALTAB(1)
        RETURN
      END IF
      IF (R_VAL .GE. RTAB(NTAB)) THEN
        VAL = VALTAB(NTAB)
        RETURN
      END IF
C
      DO I = 1, NTAB - 1
        IF ((R_VAL .GE. RTAB(I)) .AND. (R_VAL .LE. RTAB(I+1))) THEN
          R0 = DMAX1(RTAB(I), R_FLOOR)
          R1 = DMAX1(RTAB(I+1), R_FLOOR)
          LOGR  = DLOG10(R_VAL)
          LOGR0 = DLOG10(R0)
          LOGR1 = DLOG10(R1)
          IF (DABS(LOGR1 - LOGR0) .GT. 1.0D-14) THEN
            U = (LOGR - LOGR0) / (LOGR1 - LOGR0)
          ELSE
            U = 0.0D0
          END IF
          VAL = VALTAB(I) + U * (VALTAB(I+1) - VALTAB(I))
          RETURN
        END IF
      END DO
C
      VAL = VALTAB(NTAB)
      RETURN
      END
C
C======================================================================
C     SUBROUTINE SHAPE8H_TL: Shape functions for Total Lagrangian
C======================================================================
      SUBROUTINE SHAPE8H_TL(XI, ETA, ZETA, XL,
     *                       XI_NODE, ETA_NODE, ZETA_NODE,
     *                       SHP, DN_DX, DN_DY, DN_DZ,
     *                       XJ, XJINV, DETJ)
      IMPLICIT NONE
      REAL*8 XI, ETA, ZETA
      REAL*8 XL(3,8)
      REAL*8 XI_NODE(8), ETA_NODE(8), ZETA_NODE(8)
      REAL*8 SHP(4,8)
      REAL*8 DN_DX(8), DN_DY(8), DN_DZ(8)
      REAL*8 XJ(3,3), XJINV(3,3), DETJ
      REAL*8 DN_DXI(8), DN_DETA(8), DN_DZETA(8)
      REAL*8 COFAC(3,3)
      INTEGER K
      REAL*8 SMALL
      PARAMETER (SMALL = 1.0D-30)
C
      DO K = 1, 8
        SHP(4,K) = 0.125D0 * (1.0D0 + XI * XI_NODE(K)) *
     *                       (1.0D0 + ETA * ETA_NODE(K)) *
     *                       (1.0D0 + ZETA * ZETA_NODE(K))
        DN_DXI(K)   = 0.125D0 * XI_NODE(K) *
     *                (1.0D0 + ETA * ETA_NODE(K)) *
     *                (1.0D0 + ZETA * ZETA_NODE(K))
        DN_DETA(K)  = 0.125D0 * ETA_NODE(K) *
     *                (1.0D0 + XI * XI_NODE(K)) *
     *                (1.0D0 + ZETA * ZETA_NODE(K))
        DN_DZETA(K) = 0.125D0 * ZETA_NODE(K) *
     *                (1.0D0 + XI * XI_NODE(K)) *
     *                (1.0D0 + ETA * ETA_NODE(K))
      END DO
C
      DO K = 1, 3
        XJ(K,1) = 0.0D0
        XJ(K,2) = 0.0D0
        XJ(K,3) = 0.0D0
      END DO
C
      DO K = 1, 8
        XJ(1,1) = XJ(1,1) + XL(1,K) * DN_DXI(K)
        XJ(1,2) = XJ(1,2) + XL(1,K) * DN_DETA(K)
        XJ(1,3) = XJ(1,3) + XL(1,K) * DN_DZETA(K)
        XJ(2,1) = XJ(2,1) + XL(2,K) * DN_DXI(K)
        XJ(2,2) = XJ(2,2) + XL(2,K) * DN_DETA(K)
        XJ(2,3) = XJ(2,3) + XL(2,K) * DN_DZETA(K)
        XJ(3,1) = XJ(3,1) + XL(3,K) * DN_DXI(K)
        XJ(3,2) = XJ(3,2) + XL(3,K) * DN_DETA(K)
        XJ(3,3) = XJ(3,3) + XL(3,K) * DN_DZETA(K)
      END DO
C
      DETJ = XJ(1,1) * (XJ(2,2) * XJ(3,3) - XJ(2,3) * XJ(3,2))
     *     - XJ(1,2) * (XJ(2,1) * XJ(3,3) - XJ(2,3) * XJ(3,1))
     *     + XJ(1,3) * (XJ(2,1) * XJ(3,2) - XJ(2,2) * XJ(3,1))
C
      IF (DABS(DETJ) .GT. SMALL) THEN
        COFAC(1,1) =  (XJ(2,2) * XJ(3,3) - XJ(2,3) * XJ(3,2))
        COFAC(1,2) = -(XJ(2,1) * XJ(3,3) - XJ(2,3) * XJ(3,1))
        COFAC(1,3) =  (XJ(2,1) * XJ(3,2) - XJ(2,2) * XJ(3,1))
        COFAC(2,1) = -(XJ(1,2) * XJ(3,3) - XJ(1,3) * XJ(3,2))
        COFAC(2,2) =  (XJ(1,1) * XJ(3,3) - XJ(1,3) * XJ(3,1))
        COFAC(2,3) = -(XJ(1,1) * XJ(3,2) - XJ(1,2) * XJ(3,1))
        COFAC(3,1) =  (XJ(1,2) * XJ(2,3) - XJ(1,3) * XJ(2,2))
        COFAC(3,2) = -(XJ(1,1) * XJ(2,3) - XJ(1,3) * XJ(2,1))
        COFAC(3,3) =  (XJ(1,1) * XJ(2,2) - XJ(1,2) * XJ(2,1))
        XJINV(1,1) = COFAC(1,1) / DETJ
        XJINV(1,2) = COFAC(2,1) / DETJ
        XJINV(1,3) = COFAC(3,1) / DETJ
        XJINV(2,1) = COFAC(1,2) / DETJ
        XJINV(2,2) = COFAC(2,2) / DETJ
        XJINV(2,3) = COFAC(3,2) / DETJ
        XJINV(3,1) = COFAC(1,3) / DETJ
        XJINV(3,2) = COFAC(2,3) / DETJ
        XJINV(3,3) = COFAC(3,3) / DETJ
      ELSE
        DO K = 1, 3
          XJINV(K,1) = 0.0D0
          XJINV(K,2) = 0.0D0
          XJINV(K,3) = 0.0D0
        END DO
      END IF
C
      DO K = 1, 8
        DN_DX(K) = DN_DXI(K)   * XJINV(1,1) +
     *             DN_DETA(K)  * XJINV(2,1) +
     *             DN_DZETA(K) * XJINV(3,1)
        DN_DY(K) = DN_DXI(K)   * XJINV(1,2) +
     *             DN_DETA(K)  * XJINV(2,2) +
     *             DN_DZETA(K) * XJINV(3,2)
        DN_DZ(K) = DN_DXI(K)   * XJINV(1,3) +
     *             DN_DETA(K)  * XJINV(2,3) +
     *             DN_DZETA(K) * XJINV(3,3)
        SHP(1,K) = DN_DX(K)
        SHP(2,K) = DN_DY(K)
        SHP(3,K) = DN_DZ(K)
      END DO
C
      RETURN
      END
C
C======================================================================
C     SUBROUTINE COMPUTE_DEFGRAD: Compute deformation gradient F
C======================================================================
      SUBROUTINE COMPUTE_DEFGRAD(ULOC, DN_DX, DN_DY, DN_DZ,
     *                            DEFGRAD, DETF)
      IMPLICIT NONE
      REAL*8 ULOC(3,8)
      REAL*8 DN_DX(8), DN_DY(8), DN_DZ(8)
      REAL*8 DEFGRAD(3,3), DETF
      INTEGER I, J, K
      REAL*8 DUDX(3,3)
C
      DO I = 1, 3
        DO J = 1, 3
          DUDX(I,J) = 0.0D0
        END DO
      END DO
C
      DO K = 1, 8
        DUDX(1,1) = DUDX(1,1) + ULOC(1,K) * DN_DX(K)
        DUDX(1,2) = DUDX(1,2) + ULOC(1,K) * DN_DY(K)
        DUDX(1,3) = DUDX(1,3) + ULOC(1,K) * DN_DZ(K)
        DUDX(2,1) = DUDX(2,1) + ULOC(2,K) * DN_DX(K)
        DUDX(2,2) = DUDX(2,2) + ULOC(2,K) * DN_DY(K)
        DUDX(2,3) = DUDX(2,3) + ULOC(2,K) * DN_DZ(K)
        DUDX(3,1) = DUDX(3,1) + ULOC(3,K) * DN_DX(K)
        DUDX(3,2) = DUDX(3,2) + ULOC(3,K) * DN_DY(K)
        DUDX(3,3) = DUDX(3,3) + ULOC(3,K) * DN_DZ(K)
      END DO
C
      DEFGRAD(1,1) = 1.0D0 + DUDX(1,1)
      DEFGRAD(1,2) = DUDX(1,2)
      DEFGRAD(1,3) = DUDX(1,3)
      DEFGRAD(2,1) = DUDX(2,1)
      DEFGRAD(2,2) = 1.0D0 + DUDX(2,2)
      DEFGRAD(2,3) = DUDX(2,3)
      DEFGRAD(3,1) = DUDX(3,1)
      DEFGRAD(3,2) = DUDX(3,2)
      DEFGRAD(3,3) = 1.0D0 + DUDX(3,3)
C
      DETF = DEFGRAD(1,1) * (DEFGRAD(2,2)*DEFGRAD(3,3)
     *                      - DEFGRAD(2,3)*DEFGRAD(3,2))
     *     - DEFGRAD(1,2) * (DEFGRAD(2,1)*DEFGRAD(3,3)
     *                      - DEFGRAD(2,3)*DEFGRAD(3,1))
     *     + DEFGRAD(1,3) * (DEFGRAD(2,1)*DEFGRAD(3,2)
     *                      - DEFGRAD(2,2)*DEFGRAD(3,1))
C
      RETURN
      END
C
C======================================================================
C     SUBROUTINE COMPUTE_GREEN_LAGRANGE: Compute Green-Lagrange strain
C======================================================================
      SUBROUTINE COMPUTE_GREEN_LAGRANGE(DEFGRAD, GLSTRAIN, STRAIN_VEC)
      IMPLICIT NONE
      REAL*8 DEFGRAD(3,3)
      REAL*8 GLSTRAIN(3,3)
      REAL*8 STRAIN_VEC(6)
      REAL*8 RCGREEN(3,3)
      INTEGER I, J, K
C
      DO I = 1, 3
        DO J = 1, 3
          RCGREEN(I,J) = 0.0D0
          DO K = 1, 3
            RCGREEN(I,J) = RCGREEN(I,J) + DEFGRAD(K,I) * DEFGRAD(K,J)
          END DO
        END DO
      END DO
C
      DO I = 1, 3
        DO J = 1, 3
          GLSTRAIN(I,J) = 0.5D0 * RCGREEN(I,J)
        END DO
        GLSTRAIN(I,I) = GLSTRAIN(I,I) - 0.5D0
      END DO
C
      STRAIN_VEC(1) = GLSTRAIN(1,1)
      STRAIN_VEC(2) = GLSTRAIN(2,2)
      STRAIN_VEC(3) = GLSTRAIN(3,3)
      STRAIN_VEC(4) = 2.0D0 * GLSTRAIN(1,2)
      STRAIN_VEC(5) = 2.0D0 * GLSTRAIN(1,3)
      STRAIN_VEC(6) = 2.0D0 * GLSTRAIN(2,3)
C
      RETURN
      END
C
C======================================================================
C     SUBROUTINE COMPUTE_STRAINRATE_TL: Compute Green-Lagrange strain rate
C======================================================================
      SUBROUTINE COMPUTE_STRAINRATE_TL(VLOC, DN_DX, DN_DY, DN_DZ,
     *                                  DEFGRAD, STRAINRATE_VEC)
      IMPLICIT NONE
      REAL*8 VLOC(3,8)
      REAL*8 DN_DX(8), DN_DY(8), DN_DZ(8)
      REAL*8 DEFGRAD(3,3)
      REAL*8 STRAINRATE_VEC(6)
      REAL*8 FDOT(3,3)
      REAL*8 EDOT(3,3)
      REAL*8 TERM1(3,3), TERM2(3,3)
      INTEGER I, J, K
C
      DO I = 1, 3
        DO J = 1, 3
          FDOT(I,J) = 0.0D0
        END DO
      END DO
C
      DO K = 1, 8
        FDOT(1,1) = FDOT(1,1) + VLOC(1,K) * DN_DX(K)
        FDOT(1,2) = FDOT(1,2) + VLOC(1,K) * DN_DY(K)
        FDOT(1,3) = FDOT(1,3) + VLOC(1,K) * DN_DZ(K)
        FDOT(2,1) = FDOT(2,1) + VLOC(2,K) * DN_DX(K)
        FDOT(2,2) = FDOT(2,2) + VLOC(2,K) * DN_DY(K)
        FDOT(2,3) = FDOT(2,3) + VLOC(2,K) * DN_DZ(K)
        FDOT(3,1) = FDOT(3,1) + VLOC(3,K) * DN_DX(K)
        FDOT(3,2) = FDOT(3,2) + VLOC(3,K) * DN_DY(K)
        FDOT(3,3) = FDOT(3,3) + VLOC(3,K) * DN_DZ(K)
      END DO
C
      DO I = 1, 3
        DO J = 1, 3
          TERM1(I,J) = 0.0D0
          TERM2(I,J) = 0.0D0
          DO K = 1, 3
            TERM1(I,J) = TERM1(I,J) + FDOT(K,I) * DEFGRAD(K,J)
            TERM2(I,J) = TERM2(I,J) + DEFGRAD(K,I) * FDOT(K,J)
          END DO
          EDOT(I,J) = 0.5D0 * (TERM1(I,J) + TERM2(I,J))
        END DO
      END DO
C
      STRAINRATE_VEC(1) = EDOT(1,1)
      STRAINRATE_VEC(2) = EDOT(2,2)
      STRAINRATE_VEC(3) = EDOT(3,3)
      STRAINRATE_VEC(4) = 2.0D0 * EDOT(1,2)
      STRAINRATE_VEC(5) = 2.0D0 * EDOT(1,3)
      STRAINRATE_VEC(6) = 2.0D0 * EDOT(2,3)
C
      RETURN
      END
C
C======================================================================
C     SUBROUTINE BUILD_BL_MATRIX: Build nonlinear B_L matrix
C======================================================================
      SUBROUTINE BUILD_BL_MATRIX(DN_DX, DN_DY, DN_DZ, DEFGRAD, BL_MAT)
      IMPLICIT NONE
      REAL*8 DN_DX(8), DN_DY(8), DN_DZ(8)
      REAL*8 DEFGRAD(3,3)
      REAL*8 BL_MAT(6,24)
      INTEGER INODE, COL, I, J
      REAL*8 F11, F12, F13, F21, F22, F23, F31, F32, F33
      REAL*8 DNX, DNY, DNZ
C
      F11 = DEFGRAD(1,1)
      F12 = DEFGRAD(1,2)
      F13 = DEFGRAD(1,3)
      F21 = DEFGRAD(2,1)
      F22 = DEFGRAD(2,2)
      F23 = DEFGRAD(2,3)
      F31 = DEFGRAD(3,1)
      F32 = DEFGRAD(3,2)
      F33 = DEFGRAD(3,3)
C
      DO I = 1, 6
        DO J = 1, 24
          BL_MAT(I,J) = 0.0D0
        END DO
      END DO
C
      DO INODE = 1, 8
        COL = 3 * (INODE - 1)
        DNX = DN_DX(INODE)
        DNY = DN_DY(INODE)
        DNZ = DN_DZ(INODE)
C
        BL_MAT(1, COL+1) = F11 * DNX
        BL_MAT(1, COL+2) = F21 * DNX
        BL_MAT(1, COL+3) = F31 * DNX
C
        BL_MAT(2, COL+1) = F12 * DNY
        BL_MAT(2, COL+2) = F22 * DNY
        BL_MAT(2, COL+3) = F32 * DNY
C
        BL_MAT(3, COL+1) = F13 * DNZ
        BL_MAT(3, COL+2) = F23 * DNZ
        BL_MAT(3, COL+3) = F33 * DNZ
C
        BL_MAT(4, COL+1) = F11 * DNY + F12 * DNX
        BL_MAT(4, COL+2) = F21 * DNY + F22 * DNX
        BL_MAT(4, COL+3) = F31 * DNY + F32 * DNX
C
        BL_MAT(5, COL+1) = F11 * DNZ + F13 * DNX
        BL_MAT(5, COL+2) = F21 * DNZ + F23 * DNX
        BL_MAT(5, COL+3) = F31 * DNZ + F33 * DNX
C
        BL_MAT(6, COL+1) = F12 * DNZ + F13 * DNY
        BL_MAT(6, COL+2) = F22 * DNZ + F23 * DNY
        BL_MAT(6, COL+3) = F32 * DNZ + F33 * DNY
      END DO
C
      RETURN
      END
C
C======================================================================
C     SUBROUTINE HENCKY_RETURN: finite-strain J2 with Hencky elasticity
C     Multiplicative split F = Fe Fp, state Cp^-1 (stored minus I).
C     be_trial = F Cp^-1 F^T; principal log strains eps = 0.5 ln(be);
C     Kirchhoff tau = lambda tr(eps) I + 2 mu eps. Yield: q <= SIGY*J
C     (Cauchy yield SIGY, plastic flow isochoric so J is unchanged by
C     the return). Radial return is exact in principal log space.
C     Outputs: PK2 stress S = F^-1 tau F^-T, updated Cp^-1 - I, plastic
C     multiplier DGAM (= PEEQ increment), elastic energy PSI per unit
C     reference volume, and final Mises Kirchhoff stress QNEW.
C======================================================================
      SUBROUTINE HENCKY_RETURN(F, CPI, AMU, ALAM, SIGY, S6, CPN,
     *                         DGAM, PSI, QNEW, IERR)
      IMPLICIT NONE
      REAL*8 F(3,3), CPI(6), AMU, ALAM, SIGY, S6(6), CPN(6)
      REAL*8 DGAM, PSI, QNEW
      INTEGER IERR
      REAL*8 FI(3,3), DETF, CP(3,3), BE(3,3), TM(3,3), W(3), V(3,3)
      REAL*8 EPS(3), ED(3), TR, EN2, Q, JY, FAC, TAUI
      REAL*8 TAU(3,3), BEN(3,3), SS(3,3), CC(3,3)
      INTEGER I, J, K, L
C
      IERR = 0
      DGAM = 0.0D0
      PSI = 0.0D0
      QNEW = 0.0D0
      DO I = 1, 6
        S6(I) = 0.0D0
        CPN(I) = CPI(I)
      END DO
C
      DETF = F(1,1)*(F(2,2)*F(3,3)-F(2,3)*F(3,2))
     *     - F(1,2)*(F(2,1)*F(3,3)-F(2,3)*F(3,1))
     *     + F(1,3)*(F(2,1)*F(3,2)-F(2,2)*F(3,1))
      IF (DETF .LE. 1.0D-12) THEN
        IERR = 1
        RETURN
      END IF
      FI(1,1) = (F(2,2)*F(3,3)-F(2,3)*F(3,2))/DETF
      FI(1,2) = (F(1,3)*F(3,2)-F(1,2)*F(3,3))/DETF
      FI(1,3) = (F(1,2)*F(2,3)-F(1,3)*F(2,2))/DETF
      FI(2,1) = (F(2,3)*F(3,1)-F(2,1)*F(3,3))/DETF
      FI(2,2) = (F(1,1)*F(3,3)-F(1,3)*F(3,1))/DETF
      FI(2,3) = (F(1,3)*F(2,1)-F(1,1)*F(2,3))/DETF
      FI(3,1) = (F(2,1)*F(3,2)-F(2,2)*F(3,1))/DETF
      FI(3,2) = (F(1,2)*F(3,1)-F(1,1)*F(3,2))/DETF
      FI(3,3) = (F(1,1)*F(2,2)-F(1,2)*F(2,1))/DETF
C
      CP(1,1) = 1.0D0 + CPI(1)
      CP(2,2) = 1.0D0 + CPI(2)
      CP(3,3) = 1.0D0 + CPI(3)
      CP(1,2) = CPI(4)
      CP(2,1) = CPI(4)
      CP(1,3) = CPI(5)
      CP(3,1) = CPI(5)
      CP(2,3) = CPI(6)
      CP(3,2) = CPI(6)
C
      DO I = 1, 3
        DO J = 1, 3
          TM(I,J) = 0.0D0
          DO K = 1, 3
            TM(I,J) = TM(I,J) + F(I,K)*CP(K,J)
          END DO
        END DO
      END DO
      DO I = 1, 3
        DO J = 1, 3
          BE(I,J) = 0.0D0
          DO K = 1, 3
            BE(I,J) = BE(I,J) + TM(I,K)*F(J,K)
          END DO
        END DO
      END DO
C
      CALL EIG3_JACOBI(BE, W, V)
      TR = 0.0D0
      DO I = 1, 3
        EPS(I) = 0.5D0 * DLOG(DMAX1(W(I), 1.0D-30))
        TR = TR + EPS(I)
      END DO
      EN2 = 0.0D0
      DO I = 1, 3
        ED(I) = EPS(I) - TR/3.0D0
        EN2 = EN2 + ED(I)*ED(I)
      END DO
      Q = 2.0D0 * AMU * DSQRT(1.5D0 * EN2)
      JY = DEXP(TR)
C
      IF (Q .GT. SIGY*JY) THEN
        DGAM = (Q - SIGY*JY) / (3.0D0*AMU)
        FAC = SIGY*JY / Q
        DO I = 1, 3
          ED(I) = ED(I) * FAC
        END DO
        Q = SIGY*JY
      END IF
      QNEW = Q
C
      PSI = 0.5D0 * ALAM * TR * TR
      DO I = 1, 3
        EPS(I) = ED(I) + TR/3.0D0
        PSI = PSI + AMU * EPS(I) * EPS(I)
      END DO
C
      DO I = 1, 3
        DO J = 1, 3
          TAU(I,J) = 0.0D0
          BEN(I,J) = 0.0D0
        END DO
      END DO
      DO K = 1, 3
        TAUI = ALAM*TR + 2.0D0*AMU*EPS(K)
        DO I = 1, 3
          DO J = 1, 3
            TAU(I,J) = TAU(I,J) + TAUI*V(I,K)*V(J,K)
            BEN(I,J) = BEN(I,J) + DEXP(2.0D0*EPS(K))*V(I,K)*V(J,K)
          END DO
        END DO
      END DO
C
      DO I = 1, 3
        DO J = 1, 3
          SS(I,J) = 0.0D0
          CC(I,J) = 0.0D0
          DO K = 1, 3
            DO L = 1, 3
              SS(I,J) = SS(I,J) + FI(I,K)*TAU(K,L)*FI(J,L)
              CC(I,J) = CC(I,J) + FI(I,K)*BEN(K,L)*FI(J,L)
            END DO
          END DO
        END DO
      END DO
C
      S6(1) = SS(1,1)
      S6(2) = SS(2,2)
      S6(3) = SS(3,3)
      S6(4) = SS(1,2)
      S6(5) = SS(1,3)
      S6(6) = SS(2,3)
      CPN(1) = CC(1,1) - 1.0D0
      CPN(2) = CC(2,2) - 1.0D0
      CPN(3) = CC(3,3) - 1.0D0
      CPN(4) = CC(1,2)
      CPN(5) = CC(1,3)
      CPN(6) = CC(2,3)
      RETURN
      END
C
C======================================================================
C     SUBROUTINE EIG3_JACOBI: eigen-decomposition of a symmetric 3x3
C     W = eigenvalues, V(:,k) = k-th unit eigenvector.
C======================================================================
      SUBROUTINE EIG3_JACOBI(A0, W, V)
      IMPLICIT NONE
      REAL*8 A0(3,3), W(3), V(3,3)
      REAL*8 A(3,3), APQ, THETA, T, C, S, TAU, AIP, AIQ, VIP, VIQ
      REAL*8 OFF
      INTEGER I, J, P, Q, SWEEP
C
      DO I = 1, 3
        DO J = 1, 3
          A(I,J) = 0.5D0*(A0(I,J) + A0(J,I))
          V(I,J) = 0.0D0
        END DO
        V(I,I) = 1.0D0
      END DO
      DO SWEEP = 1, 30
        OFF = DABS(A(1,2)) + DABS(A(1,3)) + DABS(A(2,3))
        IF (OFF .LE. 1.0D-15*(DABS(A(1,1))+DABS(A(2,2))
     *      +DABS(A(3,3)))) GO TO 100
        DO P = 1, 2
          DO Q = P+1, 3
            APQ = A(P,Q)
            IF (DABS(APQ) .GT. 1.0D-300) THEN
              THETA = (A(Q,Q) - A(P,P)) / (2.0D0*APQ)
              IF (THETA .GE. 0.0D0) THEN
                T = 1.0D0/(THETA + DSQRT(1.0D0 + THETA*THETA))
              ELSE
                T = -1.0D0/(-THETA + DSQRT(1.0D0 + THETA*THETA))
              END IF
              C = 1.0D0/DSQRT(1.0D0 + T*T)
              S = T*C
              TAU = S/(1.0D0 + C)
              A(P,P) = A(P,P) - T*APQ
              A(Q,Q) = A(Q,Q) + T*APQ
              A(P,Q) = 0.0D0
              A(Q,P) = 0.0D0
              DO I = 1, 3
                IF ((I .NE. P) .AND. (I .NE. Q)) THEN
                  AIP = A(I,P)
                  AIQ = A(I,Q)
                  A(I,P) = AIP - S*(AIQ + TAU*AIP)
                  A(P,I) = A(I,P)
                  A(I,Q) = AIQ + S*(AIP - TAU*AIQ)
                  A(Q,I) = A(I,Q)
                END IF
              END DO
              DO I = 1, 3
                VIP = V(I,P)
                VIQ = V(I,Q)
                V(I,P) = VIP - S*(VIQ + TAU*VIP)
                V(I,Q) = VIQ + S*(VIP - TAU*VIQ)
              END DO
            END IF
          END DO
        END DO
      END DO
  100 CONTINUE
      W(1) = A(1,1)
      W(2) = A(2,2)
      W(3) = A(3,3)
      RETURN
      END
