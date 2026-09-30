C     Job-specific copy of uel/VUEL.for for the T5 embedding smoke test
C     (verification/make_t5_uel_embed.py). No VUMAT needed here -- fibers
C     use a plain *Elastic material; this test isolates the host-formulation
C     / embedded-element question only.
C======================================================================
C     VUEL: 8-Node Hexahedral Element - TOTAL LAGRANGIAN FORMULATION
C     
C     Formulation: Total Lagrangian, St. Venant-Kirchhoff Hyperelastic
C     Strain: Green-Lagrange E = 0.5*(F^T*F - I)
C     Stress: Second Piola-Kirchhoff S = C:E
C     Integration: Full 2x2x2 Gauss Quadrature
C     DOFs: 3 per node (translations)
C     Damping: Stiffness-proportional Rayleigh + Bulk viscosity
C     
C     Key differences from small strain formulation:
C       1. Deformation gradient F computed at each Gauss point
C       2. Green-Lagrange strain E = 0.5*(F^T*F - I)
C       3. Nonlinear B_L matrix (depends on current displacement)
C       4. Second Piola-Kirchhoff stress S (work-conjugate to E)
C       5. Internal force: f = integral(B_L^T * S * dV_0)
C       6. All integrals over reference configuration (dV_0)
C
C     Props array:
C       props(1) = Young's modulus E [Pa]
C       props(2) = Poisson's ratio nu [-]
C       props(3) = Density rho [kg/m^3]
C       props(4) = Rayleigh damping beta [s]
C       props(5) = Linear bulk viscosity b1 [-] (typical: 0.06)
C       props(6) = Quadratic bulk viscosity b2 [-] (typical: 1.2)
C
C     State variables (nsvars = 48):
C       svars(1:6)   = PK2 stress at GP 1 (S11, S22, S33, S12, S13, S23)
C       svars(7:12)  = PK2 stress at GP 2
C       ...
C       svars(43:48) = PK2 stress at GP 8
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
C     Deformation gradient and strain (NEW for Total Lagrangian)
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
      REAL*8 ELVOL, ELKE, ELIE
      REAL*8 CWAVE, CHARLEN, DTELEM
C
C     Loop indices and utilities
      INTEGER KBLOCK, IGAUSS, I, J, K, II, JJ
      INTEGER IDOF, JDOF, INODE, JNODE
      REAL*8 DVOL, FACTOR
      REAL*8 SMALL
      PARAMETER (SMALL = 1.0D-30)
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
C
C     Lame parameters (same as small strain)
      ALAMBDA = EMOD * ENU / ((1.0D0 + ENU) * (1.0D0 - 2.0D0 * ENU))
      AMU     = EMOD / (2.0D0 * (1.0D0 + ENU))
C
C----------------------------------------------------------------------
C     Build 3D isotropic elasticity matrix (same for St. Venant-Kirchhoff)
C     This relates PK2 stress to Green-Lagrange strain: S = C:E
C     Voigt notation order: 11, 22, 33, 12, 13, 23
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
        WRITE(*,*) '=== VUEL TOTAL LAGRANGIAN: FIRST CALL ==='
        WRITE(*,*) 'E =', EMOD, ' nu =', ENU, ' rho =', DENS
        WRITE(*,*) 'beta_Rayleigh =', BETA_RAYLEIGH
        WRITE(*,*) 'b1_bulk =', B1_BULK, ' b2_bulk =', B2_BULK
        WRITE(*,*) 'lambda =', ALAMBDA, ' mu =', AMU
        WRITE(*,*) 'nblock =', nblock, ' nnode =', nnode
        WRITE(*,*) 'ndofel =', ndofel, ' nsvars =', nsvars
      END IF
C
      DO KBLOCK = 1, nblock
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
          END DO
        END DO
C
C       Flatten into vectors
        DO INODE = 1, 8
          DO I = 1, 3
            IDOF = (INODE - 1) * 3 + I
            UVEC(IDOF) = ULOC(I, INODE)
            VVEC(IDOF) = VLOC(I, INODE)
          END DO
        END DO
C
C======================================================================
C       OPERATION CODE: MASS MATRIX CALCULATION
C       Note: Mass matrix uses REFERENCE configuration (unchanged)
C======================================================================
        IF (lflags(iOpCode) .EQ. jMassCalc) THEN
C
          DO I = 1, ndofel
            DO J = 1, ndofel
              amass(KBLOCK, I, J) = 0.0D0
            END DO
          END DO
C
          ELVOL = 0.0D0
C
          DO IGAUSS = 1, 8
            XI   = XIGP(IGAUSS)
            ETA  = ETGP(IGAUSS)
            ZETA = ZEGP(IGAUSS)
            WT   = 1.0D0
C
C           Compute shape functions and Jacobian w.r.t. REFERENCE config
            CALL SHAPE8H_TL(XI, ETA, ZETA, XLOC,
     *                      XI_NODE, ETA_NODE, ZETA_NODE,
     *                      SHP, DN_DX, DN_DY, DN_DZ,
     *                      XJ, XJINV, DETJ0)
C
            DVOL = DETJ0 * WT
            ELVOL = ELVOL + DVOL
          END DO
C
          ELEMASS = DENS * ELVOL
C
C         Lumped mass: distribute equally to all nodes
          DO INODE = 1, 8
            DO I = 1, 3
              IDOF = (INODE - 1) * 3 + I
              amass(KBLOCK, IDOF, IDOF) = ELEMASS / 8.0D0
            END DO
          END DO
C
          IF (NCALLS .LE. 5) THEN
            WRITE(*,*) '--- MASS CALC (TL) --- call #', NCALLS
            WRITE(*,*) 'Reference ELVOL =', ELVOL
            WRITE(*,*) 'ELEMASS =', ELEMASS
          END IF
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
          ELVOL = 0.0D0
          DAMP_DISSIP = 0.0D0
          BV_DISSIP = 0.0D0
C
C         Wave speed (dilatational) - reference configuration
          CWAVE = DSQRT((ALAMBDA + 2.0D0 * AMU) / DENS)
C
C         Loop over Gauss points
          DO IGAUSS = 1, 8
            XI   = XIGP(IGAUSS)
            ETA  = ETGP(IGAUSS)
            ZETA = ZEGP(IGAUSS)
            WT   = 1.0D0
C
C           ----------------------------------------------------------
C           Step 1: Compute shape function derivatives w.r.t. REFERENCE
C           ----------------------------------------------------------
            CALL SHAPE8H_TL(XI, ETA, ZETA, XLOC,
     *                      XI_NODE, ETA_NODE, ZETA_NODE,
     *                      SHP, DN_DX, DN_DY, DN_DZ,
     *                      XJ, XJINV, DETJ0)
C
            IF (DETJ0 .LE. 0.0D0) THEN
              WRITE(*,*) '*** NEGATIVE REF JACOBIAN at GP', IGAUSS
              WRITE(*,*) 'DETJ0 =', DETJ0
            END IF
C
            DVOL = DETJ0 * WT
            ELVOL = ELVOL + DVOL
C
C           ----------------------------------------------------------
C           Step 2: Compute DEFORMATION GRADIENT F
C           F_iJ = delta_iJ + du_i/dX_J
C           ----------------------------------------------------------
            CALL COMPUTE_DEFGRAD(ULOC, DN_DX, DN_DY, DN_DZ,
     *                           DEFGRAD, DETF)
C
C           ----------------------------------------------------------
C           Step 3: Compute GREEN-LAGRANGE STRAIN E
C           E = 0.5*(F^T * F - I) = 0.5*(C - I)
C           ----------------------------------------------------------
            CALL COMPUTE_GREEN_LAGRANGE(DEFGRAD, GLSTRAIN, STRAIN_VEC)
C
C           ----------------------------------------------------------
C           Step 4: Compute GREEN-LAGRANGE STRAIN RATE
C           Edot_IJ = 0.5*(F_kI * Fdot_kJ + Fdot_kI * F_kJ)
C           where Fdot = dv/dX (velocity gradient w.r.t. reference)
C           ----------------------------------------------------------
            CALL COMPUTE_STRAINRATE_TL(VLOC, DN_DX, DN_DY, DN_DZ,
     *                                  DEFGRAD, STRAINRATE_VEC)
C
C           ----------------------------------------------------------
C           Step 5: Build NONLINEAR B_L MATRIX
C           This matrix relates strain variation to displacement variation
C           delta_E = B_L * delta_u
C           B_L depends on current deformation gradient F
C           ----------------------------------------------------------
            CALL BUILD_BL_MATRIX(DN_DX, DN_DY, DN_DZ, DEFGRAD, BL_MAT)
C
C           ----------------------------------------------------------
C           Step 6: Compute PK2 STRESS (St. Venant-Kirchhoff)
C           S = C : E
C           ----------------------------------------------------------
            DO I = 1, 6
              STRESS_PK2(I) = 0.0D0
              DO J = 1, 6
                STRESS_PK2(I) = STRESS_PK2(I) + CMAT(I,J) * STRAIN_VEC(J)
              END DO
            END DO
C
C           ----------------------------------------------------------
C           Step 7: Compute VISCOUS STRESS (Rayleigh damping on PK2)
C           S_visc = beta * C : Edot
C           ----------------------------------------------------------
            DO I = 1, 6
              STRESS_VISC(I) = 0.0D0
              DO J = 1, 6
                STRESS_VISC(I) = STRESS_VISC(I) 
     *                           + BETA_RAYLEIGH * CMAT(I,J) * STRAINRATE_VEC(J)
              END DO
            END DO
C
C           ----------------------------------------------------------
C           Step 8: Compute BULK VISCOSITY (compression only)
C           Uses volumetric strain rate from det(F)
C           ----------------------------------------------------------
            EVDOT = STRAINRATE_VEC(1) + STRAINRATE_VEC(2) 
     *              + STRAINRATE_VEC(3)
C
            DO I = 1, 6
              STRESS_BULK(I) = 0.0D0
            END DO
            QBULK = 0.0D0
C
            IF (EVDOT .LT. 0.0D0) THEN
              CHARLEN = DVOL ** (1.0D0 / 3.0D0)
              QBULK = DENS * CHARLEN * (
     *                B1_BULK * CWAVE * DABS(EVDOT) +
     *                B2_BULK * CHARLEN * EVDOT * EVDOT )
C
              STRESS_BULK(1) = -QBULK
              STRESS_BULK(2) = -QBULK
              STRESS_BULK(3) = -QBULK
            END IF
C
C           ----------------------------------------------------------
C           Step 9: Total PK2 stress
C           ----------------------------------------------------------
            DO I = 1, 6
              STRESS_TOTAL(I) = STRESS_PK2(I) + STRESS_VISC(I) 
     *                          + STRESS_BULK(I)
            END DO
C
C           Store stress in state variables
            DO I = 1, 6
              svars(KBLOCK, (IGAUSS-1)*6 + I) = STRESS_TOTAL(I)
            END DO
C
C           ----------------------------------------------------------
C           Step 10: INTERNAL FORCE
C           f_int = integral(B_L^T * S * dV_0)
C           Note: Integration over REFERENCE volume
C           ----------------------------------------------------------
            DO I = 1, 24
              DO J = 1, 6
                FINT(I) = FINT(I) + BL_MAT(J,I) * STRESS_TOTAL(J) * DVOL
              END DO
            END DO
C
C           ----------------------------------------------------------
C           Energy calculations
C           ----------------------------------------------------------
C           Internal energy: U = 0.5 * integral(S : E * dV_0)
            DO I = 1, 6
              ELIE = ELIE + 0.5D0 * STRESS_PK2(I) * STRAIN_VEC(I) * DVOL
            END DO
C
C           Rayleigh dissipation
            DO I = 1, 6
              DAMP_DISSIP = DAMP_DISSIP 
     *                      + STRESS_VISC(I) * STRAINRATE_VEC(I) * DVOL * dtimeCur
            END DO
C
C           Bulk viscosity dissipation
            IF (EVDOT .LT. 0.0D0) THEN
              BV_DISSIP = BV_DISSIP 
     *                    + QBULK * DABS(EVDOT) * DVOL * dtimeCur
            END IF
C
          END DO
C
C         Assemble RHS
          DO I = 1, 24
            rhs(KBLOCK, I) = FINT(I)
          END DO
C
C         Kinetic energy
          ELEMASS = DENS * ELVOL
          DO INODE = 1, 8
            DO I = 1, 3
              ELKE = ELKE + 0.5D0 * (ELEMASS / 8.0D0) *
     *                      VLOC(I, INODE) * VLOC(I, INODE)
            END DO
          END DO
C
C         Update energy array
          energy(KBLOCK, iElIe) = ELIE
          energy(KBLOCK, iElKe) = ELKE
          energy(KBLOCK, iElDd) = energy(KBLOCK, iElDd) + DAMP_DISSIP
          energy(KBLOCK, iElBv) = energy(KBLOCK, iElBv) + BV_DISSIP
C
C         ----------------------------------------------------------
C         Stable time increment
C         For finite strain, wave speed changes with deformation
C         Conservative estimate using reference wave speed
C         ----------------------------------------------------------
          CHARLEN = ELVOL ** (1.0D0 / 3.0D0)
          OMEGA_MAX = CWAVE / CHARLEN * 2.0D0
          XI_DAMP = BETA_RAYLEIGH * OMEGA_MAX / 2.0D0
          DTELEM = (2.0D0 / OMEGA_MAX) * 
     *             (DSQRT(1.0D0 + XI_DAMP*XI_DAMP) - XI_DAMP)
          DTELEM = 0.8D0 * DTELEM
C
          dtimeStable(KBLOCK) = DTELEM
C
C         Debug output
          IF (NCALLS .LE. 10 .OR. MOD(NCALLS, 1000) .EQ. 0) THEN
            WRITE(*,*) '--- FINT (TL) --- call #', NCALLS
            WRITE(*,*) 'time =', time(iTotalTime)
            WRITE(*,*) 'DETF (last GP) =', DETF
            WRITE(*,*) 'E11, E22, E33 =', STRAIN_VEC(1), STRAIN_VEC(2),
     *                  STRAIN_VEC(3)
            WRITE(*,*) 'S11, S22, S33 =', STRESS_PK2(1), STRESS_PK2(2),
     *                  STRESS_PK2(3)
            WRITE(*,*) 'ELIE =', ELIE, ' ELKE =', ELKE
            WRITE(*,*) 'DTELEM =', DTELEM
          END IF
C
        END IF
C
C======================================================================
C       OPERATION CODE: EXTERNAL FORCE
C======================================================================
        IF (lflags(iOpCode) .EQ. jExternForce) THEN
C         External forces applied via *CLOAD in input file
        END IF
C
      END DO
C
      RETURN
      END
C
C======================================================================
C     SUBROUTINE SHAPE8H_TL: Shape functions for Total Lagrangian
C     
C     Computes shape functions and their derivatives with respect
C     to REFERENCE (material) coordinates X
C======================================================================
      SUBROUTINE SHAPE8H_TL(XI, ETA, ZETA, XL,
     *                       XI_NODE, ETA_NODE, ZETA_NODE,
     *                       SHP, DN_DX, DN_DY, DN_DZ,
     *                       XJ, XJINV, DETJ)
C
      IMPLICIT NONE
C
      REAL*8 XI, ETA, ZETA
      REAL*8 XL(3,8)
      REAL*8 XI_NODE(8), ETA_NODE(8), ZETA_NODE(8)
      REAL*8 SHP(4,8)
      REAL*8 DN_DX(8), DN_DY(8), DN_DZ(8)
      REAL*8 XJ(3,3), XJINV(3,3), DETJ
C
      REAL*8 DN_DXI(8), DN_DETA(8), DN_DZETA(8)
      REAL*8 COFAC(3,3)
      INTEGER K
      REAL*8 SMALL
      PARAMETER (SMALL = 1.0D-30)
C
C----------------------------------------------------------------------
C     Shape functions and derivatives in natural coordinates
C----------------------------------------------------------------------
      DO K = 1, 8
        SHP(4,K) = 0.125D0 * (1.0D0 + XI * XI_NODE(K)) *
     *                       (1.0D0 + ETA * ETA_NODE(K)) *
     *                       (1.0D0 + ZETA * ZETA_NODE(K))
C
        DN_DXI(K)   = 0.125D0 * XI_NODE(K) *
     *                (1.0D0 + ETA * ETA_NODE(K)) *
     *                (1.0D0 + ZETA * ZETA_NODE(K))
C
        DN_DETA(K)  = 0.125D0 * ETA_NODE(K) *
     *                (1.0D0 + XI * XI_NODE(K)) *
     *                (1.0D0 + ZETA * ZETA_NODE(K))
C
        DN_DZETA(K) = 0.125D0 * ZETA_NODE(K) *
     *                (1.0D0 + XI * XI_NODE(K)) *
     *                (1.0D0 + ETA * ETA_NODE(K))
      END DO
C
C----------------------------------------------------------------------
C     Build Jacobian matrix (reference configuration)
C     J_iJ = dX_i/dxi_J
C----------------------------------------------------------------------
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
C
        XJ(2,1) = XJ(2,1) + XL(2,K) * DN_DXI(K)
        XJ(2,2) = XJ(2,2) + XL(2,K) * DN_DETA(K)
        XJ(2,3) = XJ(2,3) + XL(2,K) * DN_DZETA(K)
C
        XJ(3,1) = XJ(3,1) + XL(3,K) * DN_DXI(K)
        XJ(3,2) = XJ(3,2) + XL(3,K) * DN_DETA(K)
        XJ(3,3) = XJ(3,3) + XL(3,K) * DN_DZETA(K)
      END DO
C
C----------------------------------------------------------------------
C     Determinant of Jacobian
C----------------------------------------------------------------------
      DETJ = XJ(1,1) * (XJ(2,2) * XJ(3,3) - XJ(2,3) * XJ(3,2))
     *     - XJ(1,2) * (XJ(2,1) * XJ(3,3) - XJ(2,3) * XJ(3,1))
     *     + XJ(1,3) * (XJ(2,1) * XJ(3,2) - XJ(2,2) * XJ(3,1))
C
C----------------------------------------------------------------------
C     Inverse of Jacobian
C----------------------------------------------------------------------
      IF (DABS(DETJ) .GT. SMALL) THEN
C
        COFAC(1,1) =  (XJ(2,2) * XJ(3,3) - XJ(2,3) * XJ(3,2))
        COFAC(1,2) = -(XJ(2,1) * XJ(3,3) - XJ(2,3) * XJ(3,1))
        COFAC(1,3) =  (XJ(2,1) * XJ(3,2) - XJ(2,2) * XJ(3,1))
C
        COFAC(2,1) = -(XJ(1,2) * XJ(3,3) - XJ(1,3) * XJ(3,2))
        COFAC(2,2) =  (XJ(1,1) * XJ(3,3) - XJ(1,3) * XJ(3,1))
        COFAC(2,3) = -(XJ(1,1) * XJ(3,2) - XJ(1,2) * XJ(3,1))
C
        COFAC(3,1) =  (XJ(1,2) * XJ(2,3) - XJ(1,3) * XJ(2,2))
        COFAC(3,2) = -(XJ(1,1) * XJ(2,3) - XJ(1,3) * XJ(2,1))
        COFAC(3,3) =  (XJ(1,1) * XJ(2,2) - XJ(1,2) * XJ(2,1))
C
        XJINV(1,1) = COFAC(1,1) / DETJ
        XJINV(1,2) = COFAC(2,1) / DETJ
        XJINV(1,3) = COFAC(3,1) / DETJ
C
        XJINV(2,1) = COFAC(1,2) / DETJ
        XJINV(2,2) = COFAC(2,2) / DETJ
        XJINV(2,3) = COFAC(3,2) / DETJ
C
        XJINV(3,1) = COFAC(1,3) / DETJ
        XJINV(3,2) = COFAC(2,3) / DETJ
        XJINV(3,3) = COFAC(3,3) / DETJ
C
      ELSE
        DO K = 1, 3
          XJINV(K,1) = 0.0D0
          XJINV(K,2) = 0.0D0
          XJINV(K,3) = 0.0D0
        END DO
      END IF
C
C----------------------------------------------------------------------
C     Global derivatives: dN/dX = dN/dxi * dxi/dX = dN/dxi * J^(-1)
C----------------------------------------------------------------------
      DO K = 1, 8
        DN_DX(K) = DN_DXI(K)   * XJINV(1,1) +
     *             DN_DETA(K)  * XJINV(2,1) +
     *             DN_DZETA(K) * XJINV(3,1)
C
        DN_DY(K) = DN_DXI(K)   * XJINV(1,2) +
     *             DN_DETA(K)  * XJINV(2,2) +
     *             DN_DZETA(K) * XJINV(3,2)
C
        DN_DZ(K) = DN_DXI(K)   * XJINV(1,3) +
     *             DN_DETA(K)  * XJINV(2,3) +
     *             DN_DZETA(K) * XJINV(3,3)
C
C       Also store in SHP for compatibility
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
C
C     F_iJ = delta_iJ + du_i/dX_J
C     
C     where du_i/dX_J = sum_a( u_i^a * dN^a/dX_J )
C======================================================================
      SUBROUTINE COMPUTE_DEFGRAD(ULOC, DN_DX, DN_DY, DN_DZ,
     *                            DEFGRAD, DETF)
C
      IMPLICIT NONE
C
      REAL*8 ULOC(3,8)
      REAL*8 DN_DX(8), DN_DY(8), DN_DZ(8)
      REAL*8 DEFGRAD(3,3), DETF
C
      INTEGER I, J, K
      REAL*8 DUDX(3,3)
C
C----------------------------------------------------------------------
C     Compute displacement gradient du_i/dX_J
C----------------------------------------------------------------------
      DO I = 1, 3
        DO J = 1, 3
          DUDX(I,J) = 0.0D0
        END DO
      END DO
C
      DO K = 1, 8
C       du1/dX, du1/dY, du1/dZ
        DUDX(1,1) = DUDX(1,1) + ULOC(1,K) * DN_DX(K)
        DUDX(1,2) = DUDX(1,2) + ULOC(1,K) * DN_DY(K)
        DUDX(1,3) = DUDX(1,3) + ULOC(1,K) * DN_DZ(K)
C       du2/dX, du2/dY, du2/dZ
        DUDX(2,1) = DUDX(2,1) + ULOC(2,K) * DN_DX(K)
        DUDX(2,2) = DUDX(2,2) + ULOC(2,K) * DN_DY(K)
        DUDX(2,3) = DUDX(2,3) + ULOC(2,K) * DN_DZ(K)
C       du3/dX, du3/dY, du3/dZ
        DUDX(3,1) = DUDX(3,1) + ULOC(3,K) * DN_DX(K)
        DUDX(3,2) = DUDX(3,2) + ULOC(3,K) * DN_DY(K)
        DUDX(3,3) = DUDX(3,3) + ULOC(3,K) * DN_DZ(K)
      END DO
C
C----------------------------------------------------------------------
C     Deformation gradient F = I + du/dX
C----------------------------------------------------------------------
      DEFGRAD(1,1) = 1.0D0 + DUDX(1,1)
      DEFGRAD(1,2) = DUDX(1,2)
      DEFGRAD(1,3) = DUDX(1,3)
C
      DEFGRAD(2,1) = DUDX(2,1)
      DEFGRAD(2,2) = 1.0D0 + DUDX(2,2)
      DEFGRAD(2,3) = DUDX(2,3)
C
      DEFGRAD(3,1) = DUDX(3,1)
      DEFGRAD(3,2) = DUDX(3,2)
      DEFGRAD(3,3) = 1.0D0 + DUDX(3,3)
C
C----------------------------------------------------------------------
C     Determinant of F (Jacobian of deformation = volume ratio)
C----------------------------------------------------------------------
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
C
C     E = 0.5 * (F^T * F - I) = 0.5 * (C - I)
C
C     where C = F^T * F is the right Cauchy-Green deformation tensor
C======================================================================
      SUBROUTINE COMPUTE_GREEN_LAGRANGE(DEFGRAD, GLSTRAIN, STRAIN_VEC)
C
      IMPLICIT NONE
C
      REAL*8 DEFGRAD(3,3)
      REAL*8 GLSTRAIN(3,3)
      REAL*8 STRAIN_VEC(6)
C
      REAL*8 RCGREEN(3,3)
      INTEGER I, J, K
C
C----------------------------------------------------------------------
C     Compute right Cauchy-Green tensor C = F^T * F
C----------------------------------------------------------------------
      DO I = 1, 3
        DO J = 1, 3
          RCGREEN(I,J) = 0.0D0
          DO K = 1, 3
            RCGREEN(I,J) = RCGREEN(I,J) + DEFGRAD(K,I) * DEFGRAD(K,J)
          END DO
        END DO
      END DO
C
C----------------------------------------------------------------------
C     Green-Lagrange strain E = 0.5 * (C - I)
C----------------------------------------------------------------------
      DO I = 1, 3
        DO J = 1, 3
          GLSTRAIN(I,J) = 0.5D0 * RCGREEN(I,J)
        END DO
        GLSTRAIN(I,I) = GLSTRAIN(I,I) - 0.5D0
      END DO
C
C----------------------------------------------------------------------
C     Convert to Voigt notation: E11, E22, E33, 2*E12, 2*E13, 2*E23
C     Note: Engineering shear strains (factor of 2) for consistency
C     with elasticity matrix formulation
C----------------------------------------------------------------------
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
C
C     Edot = 0.5 * (Fdot^T * F + F^T * Fdot)
C
C     where Fdot_iJ = dv_i/dX_J (velocity gradient w.r.t. reference)
C======================================================================
      SUBROUTINE COMPUTE_STRAINRATE_TL(VLOC, DN_DX, DN_DY, DN_DZ,
     *                                  DEFGRAD, STRAINRATE_VEC)
C
      IMPLICIT NONE
C
      REAL*8 VLOC(3,8)
      REAL*8 DN_DX(8), DN_DY(8), DN_DZ(8)
      REAL*8 DEFGRAD(3,3)
      REAL*8 STRAINRATE_VEC(6)
C
      REAL*8 FDOT(3,3)
      REAL*8 EDOT(3,3)
      REAL*8 TERM1(3,3), TERM2(3,3)
      INTEGER I, J, K
C
C----------------------------------------------------------------------
C     Compute velocity gradient Fdot_iJ = dv_i/dX_J
C----------------------------------------------------------------------
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
C
        FDOT(2,1) = FDOT(2,1) + VLOC(2,K) * DN_DX(K)
        FDOT(2,2) = FDOT(2,2) + VLOC(2,K) * DN_DY(K)
        FDOT(2,3) = FDOT(2,3) + VLOC(2,K) * DN_DZ(K)
C
        FDOT(3,1) = FDOT(3,1) + VLOC(3,K) * DN_DX(K)
        FDOT(3,2) = FDOT(3,2) + VLOC(3,K) * DN_DY(K)
        FDOT(3,3) = FDOT(3,3) + VLOC(3,K) * DN_DZ(K)
      END DO
C
C----------------------------------------------------------------------
C     Edot = 0.5 * (Fdot^T * F + F^T * Fdot)
C----------------------------------------------------------------------
C     Term1 = Fdot^T * F
      DO I = 1, 3
        DO J = 1, 3
          TERM1(I,J) = 0.0D0
          DO K = 1, 3
            TERM1(I,J) = TERM1(I,J) + FDOT(K,I) * DEFGRAD(K,J)
          END DO
        END DO
      END DO
C
C     Term2 = F^T * Fdot
      DO I = 1, 3
        DO J = 1, 3
          TERM2(I,J) = 0.0D0
          DO K = 1, 3
            TERM2(I,J) = TERM2(I,J) + DEFGRAD(K,I) * FDOT(K,J)
          END DO
        END DO
      END DO
C
C     Edot = 0.5 * (Term1 + Term2)
      DO I = 1, 3
        DO J = 1, 3
          EDOT(I,J) = 0.5D0 * (TERM1(I,J) + TERM2(I,J))
        END DO
      END DO
C
C----------------------------------------------------------------------
C     Convert to Voigt notation (engineering shear rates)
C----------------------------------------------------------------------
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
C
C     The B_L matrix relates strain variation to displacement variation:
C     delta_E = B_L * delta_u
C
C     For Green-Lagrange strain in Voigt notation:
C     delta_E_IJ = F_kI * delta(du_k/dX_J)  (symmetric part)
C
C     This leads to:
C     B_L(I,a*3+k) involves F_kI * dN^a/dX_J terms
C
C     The structure is more complex than linear B because F appears
C======================================================================
      SUBROUTINE BUILD_BL_MATRIX(DN_DX, DN_DY, DN_DZ, DEFGRAD, BL_MAT)
C
      IMPLICIT NONE
C
      REAL*8 DN_DX(8), DN_DY(8), DN_DZ(8)
      REAL*8 DEFGRAD(3,3)
      REAL*8 BL_MAT(6,24)
C
      INTEGER INODE, COL
      REAL*8 F11, F12, F13, F21, F22, F23, F31, F32, F33
      REAL*8 DNX, DNY, DNZ
      INTEGER I, J
C
C----------------------------------------------------------------------
C     Extract deformation gradient components for clarity
C----------------------------------------------------------------------
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
C----------------------------------------------------------------------
C     Initialize B_L matrix
C----------------------------------------------------------------------
      DO I = 1, 6
        DO J = 1, 24
          BL_MAT(I,J) = 0.0D0
        END DO
      END DO
C
C----------------------------------------------------------------------
C     Build B_L matrix for each node
C
C     The variation of Green-Lagrange strain is:
C     delta_E_IJ = 0.5 * (F_kI * delta_Hkj + F_kJ * delta_HkI)
C     where H_kJ = du_k/dX_J and delta_H_kJ = sum_a(delta_u_k^a * dN^a/dX_J)
C
C     For Voigt notation [E11, E22, E33, 2*E12, 2*E13, 2*E23]:
C
C     Row 1 (E11): delta_E11 = F_k1 * delta_Hk1
C                 = F11*dN/dX*du1 + F21*dN/dX*du2 + F31*dN/dX*du3
C
C     Row 2 (E22): delta_E22 = F_k2 * delta_Hk2
C                 = F12*dN/dY*du1 + F22*dN/dY*du2 + F32*dN/dY*du3
C
C     Row 3 (E33): delta_E33 = F_k3 * delta_Hk3
C                 = F13*dN/dZ*du1 + F23*dN/dZ*du2 + F33*dN/dZ*du3
C
C     Row 4 (2*E12): 2*delta_E12 = F_k1*delta_Hk2 + F_k2*delta_Hk1
C
C     Row 5 (2*E13): 2*delta_E13 = F_k1*delta_Hk3 + F_k3*delta_Hk1
C
C     Row 6 (2*E23): 2*delta_E23 = F_k2*delta_Hk3 + F_k3*delta_Hk2
C----------------------------------------------------------------------
C
      DO INODE = 1, 8
        COL = 3 * (INODE - 1)
        DNX = DN_DX(INODE)
        DNY = DN_DY(INODE)
        DNZ = DN_DZ(INODE)
C
C       Row 1: E11 contribution
C       delta_E11 = F11*dN/dX*du1 + F21*dN/dX*du2 + F31*dN/dX*du3
        BL_MAT(1, COL+1) = F11 * DNX
        BL_MAT(1, COL+2) = F21 * DNX
        BL_MAT(1, COL+3) = F31 * DNX
C
C       Row 2: E22 contribution
C       delta_E22 = F12*dN/dY*du1 + F22*dN/dY*du2 + F32*dN/dY*du3
        BL_MAT(2, COL+1) = F12 * DNY
        BL_MAT(2, COL+2) = F22 * DNY
        BL_MAT(2, COL+3) = F32 * DNY
C
C       Row 3: E33 contribution
C       delta_E33 = F13*dN/dZ*du1 + F23*dN/dZ*du2 + F33*dN/dZ*du3
        BL_MAT(3, COL+1) = F13 * DNZ
        BL_MAT(3, COL+2) = F23 * DNZ
        BL_MAT(3, COL+3) = F33 * DNZ
C
C       Row 4: 2*E12 contribution
C       2*delta_E12 = (F11*dN/dY + F12*dN/dX)*du1 
C                   + (F21*dN/dY + F22*dN/dX)*du2
C                   + (F31*dN/dY + F32*dN/dX)*du3
        BL_MAT(4, COL+1) = F11 * DNY + F12 * DNX
        BL_MAT(4, COL+2) = F21 * DNY + F22 * DNX
        BL_MAT(4, COL+3) = F31 * DNY + F32 * DNX
C
C       Row 5: 2*E13 contribution
C       2*delta_E13 = (F11*dN/dZ + F13*dN/dX)*du1
C                   + (F21*dN/dZ + F23*dN/dX)*du2
C                   + (F31*dN/dZ + F33*dN/dX)*du3
        BL_MAT(5, COL+1) = F11 * DNZ + F13 * DNX
        BL_MAT(5, COL+2) = F21 * DNZ + F23 * DNX
        BL_MAT(5, COL+3) = F31 * DNZ + F33 * DNX
C
C       Row 6: 2*E23 contribution
C       2*delta_E23 = (F12*dN/dZ + F13*dN/dY)*du1
C                   + (F22*dN/dZ + F23*dN/dY)*du2
C                   + (F32*dN/dZ + F33*dN/dY)*du3
        BL_MAT(6, COL+1) = F12 * DNZ + F13 * DNY
        BL_MAT(6, COL+2) = F22 * DNZ + F23 * DNY
        BL_MAT(6, COL+3) = F32 * DNZ + F33 * DNY
C
      END DO
C
      RETURN
      END
