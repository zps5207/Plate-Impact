C======================================================================
C     VUEL_FAILURE_VOL_CORR: 8-Node Hexahedral Element - TOTAL LAGRANGIAN
C     FORMULATION WITH PREPROCESSED HOST VOLUME FRACTION CORRECTION (T-005 DRAFT)
C
C     Branched from uel/VUEL_failure.for for exploratory development of
C     volume-based host matrix correction (Task T-005).
C
C     KEY ARCHITECTURAL DIFFERENCE FROM STAGE 7:
C       Stage 7 (committed, shipped) scaled matrix material constants
C       (E_k, lambda_k, mu_k, sigy0_k, Hmod_k) by eta_k = 1 - Vf inside VUEL.
C       This draft leaves ALL matrix material constants UNTOUCHED at baseline
C       values (E0, nu0, rho0, sigy0, Hmod0) and instead scales the differential
C       integration volume:
C         dVol_eff = eta_k * dVol_geom  (where dVol_geom = detJ0 * WT)
C         ELVOL_EFF = eta_k * ELVOL_GEOM
C       
C     BENEFITS OF VOLUME-SCALING FORMULATION:
C       1. Dilatational wave speed c_0 = sqrt((lambda_0 + 2*mu_0)/rho_0) is
C          exact and unapproximated, since material moduli and density are unscaled.
C       2. Stable time step dtimeStable = 0.8 * (2 / omega_max) is derived
C          rigorously using geometric characteristic length CHARLEN = (ELVOL_GEOM)^(1/3)
C          and exact matrix wave speed c_0.
C       3. Host lumped mass matrix amass = (rho_0 * ELVOL_EFF) / 8.0D0 scales
C          naturally with host matrix volume fraction (1 - Vf), eliminating
C          mass double-counting against embedded fibers.
C       4. Radial return plastic multiplier DGAMMA, plastic strain increment DEp,
C          and PEEQ evolution are algebraically identical to Stage 7.
C
C     State variables (nsvars = 107):
C       svars(1:48)   = PK2 stress tensor across 8 Gauss points
C       svars(49)     = element failure flag: 0.0 = intact, 1.0 = failed
C       svars(50:105) = plastic strain (6) + PEEQ (1) across 8 Gauss points
C       svars(106)    = damage fraction D (0.0 to 1.0)
C       svars(107)    = per-element fiber volume fraction Vf initialized
C                       via *Initial Conditions, TYPE=SOLUTION.
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
C     Material properties (UNTOUCHED BASELINE)
      REAL*8 EMOD, ENU, DENS, BETA_RAYLEIGH
      REAL*8 ALAMBDA, AMU, BULK_MODULUS
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
C     Damping, energy, and volume variables
      REAL*8 OMEGA_MAX, XI_DAMP
      REAL*8 DAMP_DISSIP, BV_DISSIP
      REAL*8 ELVOL_GEOM, ELVOL_EFF, DVOL_GEOM, DVOL_EFF
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
C     Failure criterion variables
      REAL*8 EPS_FAIL
      REAL*8 STRETCH1, STRETCH2, STRETCH3
      REAL*8 ENG1, ENG2, ENG3, MAXABS_ENG
      REAL*8 ELEM_MAXABS_ENG
      LOGICAL ELEM_ALREADY_FAILED
C
C     Plasticity variables (UNTOUCHED BASELINE MODULI)
      REAL*8 SIGY0, HMOD, IPLAST
      REAL*8 JAC_FAIL, ELEM_MIN_DETF
      REAL*8 EP_VEC(6), PEEQ_OLD
      REAL*8 EE_TRIAL_VEC(6), S_TRIAL_VEC(6), EE_NEW_VEC(6)
      REAL*8 DEP_VEC(6), SDEV(6)
      REAL*8 P_HYDRO, SIGMA_TRIAL, SIGY_OLD, SIGY_NEW, DGAMMA
      REAL*8 PLASTIC_DISSIP
      INTEGER IGPBASE
C
C     Stage 5 post-failure degradation and volume fraction scaling
      REAL*8 DEGRADE_TIME, COMP_RESIDUAL_FRAC
      REAL*8 FIBER_VOL_FRAC, ETA_VF_RAW, ETA_VF
      REAL*8 DAMAGE, DAMAGE_OLD, STRESS_SCALE
      REAL*8 VOL_ELASTIC_STRAIN, P_RESIDUAL
      REAL*8 STRESS_RESIDUAL(6)
      LOGICAL CONSTITUTIVE_ACTIVE
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
C     Extract material properties (UNTOUCHED BASELINE PARAMETERS)
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
C     Lame parameters (UNTOUCHED MATRIX MATERIAL CONSTANTS)
      ALAMBDA = EMOD * ENU / ((1.0D0 + ENU) * (1.0D0 - 2.0D0 * ENU))
      AMU     = EMOD / (2.0D0 * (1.0D0 + ENU))
      BULK_MODULUS = ALAMBDA + 2.0D0*AMU/3.0D0
C
C----------------------------------------------------------------------
C     Build 3D isotropic elasticity matrix (Shared baseline CMAT)
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
        WRITE(*,*) '=== VUEL VOL-SCALED FORMULATION (T-005 DRAFT) ==='
        WRITE(*,*) 'E0 =', EMOD, ' nu0 =', ENU, ' rho0 =', DENS
        WRITE(*,*) 'SIGY0 =', SIGY0, ' HMOD =', HMOD, ' IPLAST =', IPLAST
        WRITE(*,*) 'lambda0 =', ALAMBDA, ' mu0 =', AMU
      END IF
C
      DO KBLOCK = 1, nblock
C       Extract per-element fiber volume fraction Vf and compute
C       host matrix volume fraction eta_k = max(1 - Vf, 1e-6)
        FIBER_VOL_FRAC = 0.0D0
        IF (nsvars .GE. 107) FIBER_VOL_FRAC = svars(KBLOCK,107)
        ETA_VF_RAW = 1.0D0 - FIBER_VOL_FRAC
        ETA_VF = DMAX1(ETA_VF_RAW, 1.0D-6)
        IF ((ETA_VF_RAW .LT. 1.0D-6) .AND. (NCALLS .LE. 5)) THEN
          WRITE(*,*) '*** VUEL VOL-SCALING CLAMP: elem =', jElem(KBLOCK),
     *               ' Vf =', FIBER_VOL_FRAC, ' eta_used =', ETA_VF
        END IF
C
C----------------------------------------------------------------------
C       Extract REFERENCE nodal coordinates, displacements, velocities
C----------------------------------------------------------------------
        DO INODE = 1, 8
          DO I = 1, 3
            XLOC(I, INODE) = coords(KBLOCK, INODE, I)
            IDOF = (INODE - 1) * 3 + I
            ULOC(I, INODE) = u(KBLOCK, IDOF)
            VLOC(I, INODE) = v(KBLOCK, IDOF)
            UVEC(IDOF) = ULOC(I, INODE)
            VVEC(IDOF) = VLOC(I, INODE)
          END DO
        END DO
C
C======================================================================
C       OPERATION CODE: MASS MATRIX CALCULATION (VOLUME SCALED)
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
          DO IGAUSS = 1, 8
            XI   = XIGP(IGAUSS)
            ETA  = ETGP(IGAUSS)
            ZETA = ZEGP(IGAUSS)
            WT   = 1.0D0
            CALL SHAPE8H_TL(XI, ETA, ZETA, XLOC,
     *                      XI_NODE, ETA_NODE, ZETA_NODE,
     *                      SHP, DN_DX, DN_DY, DN_DZ,
     *                      XJ, XJINV, DETJ0)
            DVOL_GEOM = DETJ0 * WT
            ELVOL_GEOM = ELVOL_GEOM + DVOL_GEOM
          END DO
C
C         Scale host reference volume by effective matrix fraction eta_k
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
          ELVOL_EFF  = 0.0D0
          DAMP_DISSIP = 0.0D0
          BV_DISSIP = 0.0D0
          PLASTIC_DISSIP = 0.0D0
C
C         Exact matrix wave speed (reference configuration)
          CWAVE = DSQRT((ALAMBDA + 2.0D0 * AMU) / DENS)
C
          ELEM_ALREADY_FAILED = (svars(KBLOCK,49) .GT. 0.5D0)
          DAMAGE_OLD = 0.0D0
          DAMAGE = 0.0D0
          IF (ELEM_ALREADY_FAILED) THEN
            IF ((DEGRADE_TIME .GT. SMALL) .AND. (nsvars .GE. 106)) THEN
              DAMAGE_OLD = DMAX1(0.0D0, DMIN1(svars(KBLOCK,106), 1.0D0))
              DAMAGE = DMIN1(1.0D0, DAMAGE_OLD + dtimeCur/DEGRADE_TIME)
            ELSE
              DAMAGE_OLD = 1.0D0
              DAMAGE = 1.0D0
            END IF
            IF (nsvars .GE. 106) svars(KBLOCK,106) = DAMAGE
          END IF
          STRESS_SCALE = DMAX1(0.0D0, 1.0D0-DAMAGE)
          CONSTITUTIVE_ACTIVE = ((.NOT. ELEM_ALREADY_FAILED) .OR.
     *                           (STRESS_SCALE .GT. SMALL))
          ELEM_MAXABS_ENG = 0.0D0
          ELEM_MIN_DETF = 1.0D30
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
            DVOL_EFF  = ETA_VF * DVOL_GEOM
            ELVOL_GEOM = ELVOL_GEOM + DVOL_GEOM
            ELVOL_EFF  = ELVOL_EFF  + DVOL_EFF
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
C           Constitutive stress update uses UNTOUCHED baseline CMAT, SIGY0, HMOD
            IGPBASE = 49 + (IGAUSS-1)*7
            DO I = 1, 6
              EP_VEC(I) = svars(KBLOCK, IGPBASE+I)
            END DO
            PEEQ_OLD = svars(KBLOCK, IGPBASE+7)
            DGAMMA = 0.0D0
            SIGY_OLD = SIGY0 + HMOD*PEEQ_OLD
            SIGY_NEW = SIGY_OLD
C
            IF (.NOT. CONSTITUTIVE_ACTIVE) THEN
              DO I = 1, 6
                STRESS_PK2(I) = 0.0D0
              END DO
            ELSE
              DO I = 1, 6
                EE_TRIAL_VEC(I) = STRAIN_VEC(I) - EP_VEC(I)
              END DO
              DO I = 1, 6
                S_TRIAL_VEC(I) = 0.0D0
                DO J = 1, 6
                  S_TRIAL_VEC(I) = S_TRIAL_VEC(I)
     *                             + CMAT(I,J) * EE_TRIAL_VEC(J)
                END DO
              END DO
C
              DO I = 1, 6
                DEP_VEC(I) = 0.0D0
              END DO
C
              IF (IPLAST .GT. 0.5D0) THEN
                P_HYDRO = (S_TRIAL_VEC(1)+S_TRIAL_VEC(2)+S_TRIAL_VEC(3))
     *                    / 3.0D0
                SDEV(1) = S_TRIAL_VEC(1) - P_HYDRO
                SDEV(2) = S_TRIAL_VEC(2) - P_HYDRO
                SDEV(3) = S_TRIAL_VEC(3) - P_HYDRO
                SDEV(4) = S_TRIAL_VEC(4)
                SDEV(5) = S_TRIAL_VEC(5)
                SDEV(6) = S_TRIAL_VEC(6)
C
                SIGMA_TRIAL = DSQRT(DMAX1(1.5D0*(
     *              SDEV(1)*SDEV(1) + SDEV(2)*SDEV(2) + SDEV(3)*SDEV(3)
     *              + 2.0D0*(SDEV(4)*SDEV(4) + SDEV(5)*SDEV(5)
     *                       + SDEV(6)*SDEV(6))), 0.0D0))
C
                IF ((SIGMA_TRIAL .GT. SIGY_OLD) .AND.
     *              ((3.0D0*AMU + HMOD) .GT. SMALL)) THEN
                  DGAMMA = (SIGMA_TRIAL - SIGY_OLD)
     *                     / (3.0D0*AMU + HMOD)
                  SIGY_NEW = SIGY_OLD + HMOD*DGAMMA
                  PEEQ_OLD = PEEQ_OLD + DGAMMA
C
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
C
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
            END IF
C
            DO I = 1, 6
              EE_NEW_VEC(I) = STRAIN_VEC(I) - EP_VEC(I)
            END DO
C
C           Rayleigh damping
            DO I = 1, 6
              STRESS_VISC(I) = 0.0D0
              DO J = 1, 6
                STRESS_VISC(I) = STRESS_VISC(I) 
     *                           + BETA_RAYLEIGH * CMAT(I,J)
     *                           * STRAINRATE_VEC(J)
              END DO
            END DO
C
C           Bulk viscosity
            EVDOT = STRAINRATE_VEC(1) + STRAINRATE_VEC(2) 
     *              + STRAINRATE_VEC(3)
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
            VOL_ELASTIC_STRAIN = EE_NEW_VEC(1) + EE_NEW_VEC(2)
     *                           + EE_NEW_VEC(3)
            DO I = 1, 6
              STRESS_RESIDUAL(I) = 0.0D0
            END DO
            P_RESIDUAL = 0.0D0
            IF (ELEM_ALREADY_FAILED .AND.
     *          (COMP_RESIDUAL_FRAC .GT. 0.0D0) .AND.
     *          (VOL_ELASTIC_STRAIN .LT. 0.0D0)) THEN
              P_RESIDUAL = COMP_RESIDUAL_FRAC * BULK_MODULUS
     *                     * VOL_ELASTIC_STRAIN
              STRESS_RESIDUAL(1) = P_RESIDUAL
              STRESS_RESIDUAL(2) = P_RESIDUAL
              STRESS_RESIDUAL(3) = P_RESIDUAL
            END IF
C
            DO I = 1, 6
              STRESS_TOTAL(I) = STRESS_SCALE *
     *                         (STRESS_PK2(I) + STRESS_VISC(I)
     *                          + STRESS_BULK(I))
     *                         + DAMAGE*STRESS_RESIDUAL(I)
            END DO
C
            DO I = 1, 6
              svars(KBLOCK, (IGAUSS-1)*6 + I) = STRESS_TOTAL(I)
            END DO
C
C           Internal force integration uses DVOL_EFF (Volume-Scaled)
            DO I = 1, 24
              DO J = 1, 6
                FINT(I) = FINT(I) + BL_MAT(J,I) * STRESS_TOTAL(J) * DVOL_EFF
              END DO
            END DO
C
C           Energy integrals use DVOL_EFF (Volume-Scaled)
            IF (CONSTITUTIVE_ACTIVE) THEN
              DO I = 1, 6
                ELIE = ELIE + 0.5D0*STRESS_SCALE*STRESS_PK2(I)
     *                         *EE_NEW_VEC(I)*DVOL_EFF
              END DO
              PLASTIC_DISSIP = PLASTIC_DISSIP
     *            + STRESS_SCALE*0.5D0*(SIGY_OLD+SIGY_NEW)
     *              *DGAMMA*DVOL_EFF
            END IF
            IF (ELEM_ALREADY_FAILED .AND.
     *          (VOL_ELASTIC_STRAIN .LT. 0.0D0) .AND.
     *          (COMP_RESIDUAL_FRAC .GT. 0.0D0)) THEN
              ELIE = ELIE + 0.5D0*DAMAGE*COMP_RESIDUAL_FRAC
     *             * BULK_MODULUS*VOL_ELASTIC_STRAIN
     *             * VOL_ELASTIC_STRAIN*DVOL_EFF
            END IF
C
            IF (STRESS_SCALE .GT. SMALL) THEN
              DO I = 1, 6
                DAMP_DISSIP = DAMP_DISSIP
     *                      + STRESS_SCALE*STRESS_VISC(I)
     *                      * STRAINRATE_VEC(I)*DVOL_EFF*dtimeCur
              END DO
              IF (EVDOT .LT. 0.0D0) THEN
                BV_DISSIP = BV_DISSIP
     *                      + STRESS_SCALE*QBULK*DABS(EVDOT)
     *                      * DVOL_EFF*dtimeCur
              END IF
            END IF
          END DO
C
          IF (.NOT. ELEM_ALREADY_FAILED) THEN
            IF (ELEM_MAXABS_ENG .GE. EPS_FAIL) THEN
              svars(KBLOCK, 49) = 1.0D0
              IF (nsvars .GE. 106) svars(KBLOCK,106) = 0.0D0
            ELSE IF ((ELEM_MIN_DETF .LE. JAC_FAIL) .OR.
     *               (ELEM_MIN_DETF .LE. 0.0D0)) THEN
              svars(KBLOCK, 49) = 1.0D0
              IF (nsvars .GE. 106) svars(KBLOCK,106) = 0.0D0
            END IF
          END IF
C
          DO I = 1, 24
            rhs(KBLOCK, I) = FINT(I)
          END DO
C
C         Kinetic energy uses ELVOL_EFF
          ELEMASS = DENS * ELVOL_EFF
          DO INODE = 1, 8
            DO I = 1, 3
              ELKE = ELKE + 0.5D0 * (ELEMASS / 8.0D0) *
     *                      VLOC(I, INODE) * VLOC(I, INODE)
            END DO
          END DO
C
          energy(KBLOCK, iElIe) = ELIE
          energy(KBLOCK, iElKe) = ELKE
          energy(KBLOCK, iElDd) = energy(KBLOCK, iElDd) + DAMP_DISSIP
          energy(KBLOCK, iElBv) = energy(KBLOCK, iElBv) + BV_DISSIP
          energy(KBLOCK, iElPd) = energy(KBLOCK, iElPd) + PLASTIC_DISSIP
C
C         Stable time increment uses GEOMETRIC volume for CHARLEN
          IF (ELEM_ALREADY_FAILED .AND.
     *        (STRESS_SCALE .LE. SMALL) .AND.
     *        (COMP_RESIDUAL_FRAC .LE. SMALL)) THEN
            dtimeStable(KBLOCK) = 1.0D30
          ELSE
            CHARLEN = ELVOL_GEOM ** (1.0D0 / 3.0D0)
            OMEGA_MAX = CWAVE / CHARLEN * 2.0D0
            XI_DAMP = BETA_RAYLEIGH * OMEGA_MAX / 2.0D0
            DTELEM = (2.0D0 / OMEGA_MAX) *
     *               (DSQRT(1.0D0 + XI_DAMP*XI_DAMP) - XI_DAMP)
            dtimeStable(KBLOCK) = 0.8D0 * DTELEM
          END IF
        END IF
C
        IF (lflags(iOpCode) .EQ. jExternForce) THEN
        END IF
      END DO
C
      RETURN
      END
