C======================================================================
C     VUINTERACTION_BASELINE: General Contact User Subroutine for
C     Embedded Fiber to Host Matrix Interaction with Baseline
C     Overclosure Tracking and Monotonic Downward Ratchet.
C
C     Task: T-056 (Plate Impact Project)
C     Target: Abaqus/Explicit 2024 (Intel Fortran, Fixed Form 72-col)
C
C     Interfacial Kinematics and Constitutive Logic:
C       1. Evaluates current penetration d = PENETRATION(K).
C       2. On first encounter (seen-flag STATE(2,1,K) < 0.5), records
C          the initial overclosure d0 = MAX(d, 0.0) and latches flag.
C       3. In subsequent increments, ratchets baseline downward:
C          d0 = MIN(d0, MAX(d, 0.0)).
C       4. Computes normal compressive pressure:
C          p = KPEN * MAX(0.0, d - d0).
C       5. Computes optional Coulomb friction with limit:
C          tau_crit = mu * p.
C
C     Properties: (*SURFACE INTERACTION, USER, PROPERTIES=2, DEPVAR=2)
C       PROPS(1) = Penalty stiffness KPEN [N/m^3] (<=0 -> STIFFDEF)
C       PROPS(2) = Coulomb friction coefficient mu (default 0.01)
C
C     State Variables (DEPVAR = 2):
C       STATE(1, 1, K) = Baseline penetration offset d0 [m]
C       STATE(2, 1, K) = Initialization flag (0.0=unseen, 1.0=seen)
C======================================================================
      SUBROUTINE VUINTERACTION (
     *     STRESS, FLUXSLV, FLUXMST,
     *     STATE, SED,
     *     SFD, SCD, SPD, SVD,
     *     NBLOCK, NBLOCKANAL, NBLOCKEDGE,
     *     NNODSTATE, NNODSLV, NNODMST, NDIR,
     *     NSTATES, NPROPS, NTEMP, NFIELDS,
     *     JFLAGS, RDATA,
     *     SURFINT, SURFSLV, SURFMST,
     *     JSLVUID, JMSTUID, PROPS,
     *     PENETRATION, DRDISP, DROT, DIRCOS, STIFFDEF, CONDUCTDEF,
     *     COORDSLV, COORDMST, AREAPROX, SHAPESLV, SHAPEMST,
     *     TEMPSLV, TEMPMST, DTEMPSLV, DTEMPMST,
     *     FIELDSLV, FIELDMST, DFIELDSLV, DFIELDMST )
C
      INCLUDE 'vaba_param.inc'
C
      CHARACTER*80 SURFINT, SURFSLV, SURFMST
      DIMENSION JFLAGS(*), RDATA(*)
      DIMENSION JSLVUID(NNODSLV, NBLOCK), JMSTUID(NNODMST, NBLOCK)
      DIMENSION PROPS(NPROPS)
      DIMENSION PENETRATION(NBLOCK), DRDISP(NDIR, NBLOCK)
      DIMENSION DROT(2, 2, NBLOCK), DIRCOS(NDIR, NDIR, NBLOCK)
      DIMENSION STIFFDEF(NBLOCK), CONDUCTDEF(NBLOCK)
      DIMENSION COORDSLV(NDIR, NNODSLV, NBLOCK), COORDMST(NDIR, NBLOCK)
      DIMENSION AREAPROX(NBLOCK)
      DIMENSION TEMPSLV(NBLOCK), TEMPMST(NBLOCK)
      DIMENSION DTEMPSLV(NBLOCK), DTEMPMST(NBLOCK)
      DIMENSION FIELDSLV(NFIELDS, NBLOCK), FIELDMST(NFIELDS, NBLOCK)
      DIMENSION DFIELDSLV(NFIELDS, NBLOCK), DFIELDMST(NFIELDS, NBLOCK)
      DIMENSION STRESS(NDIR, NBLOCK), FLUXSLV(NBLOCK), FLUXMST(NBLOCK)
      DIMENSION STATE(NSTATES, NNODSTATE, NBLOCK)
      DIMENSION SED(NBLOCK), SFD(NBLOCK), SCD(NBLOCK), SPD(NBLOCK),
     *          SVD(NBLOCK)
C
      INTEGER K, IDIR
      REAL*8 D, D_POS, D0, D_EFF, PRESS, KPEN, FRIC, KS
      REAL*8 DS1, DS2, TAU1, TAU2, TAU_MAG, TAU_CRIT, SCALE
      INTEGER NCALL, NPRT, LOUT, J, IU
      LOGICAL LOPEN
      CHARACTER*256 OUTDIR
      INTEGER LENOUT
      REAL*8 DMIN, DMAX, SMAX, ST1IN, ST2IN, S1IN
      SAVE NCALL, NPRT, LOPEN
      DATA NCALL /0/, NPRT /0/, LOPEN /.FALSE./
C
C     DIAGNOSTIC: log to <outdir>/vuint_diag.txt (unit 117)
      IU = 117
      NCALL = NCALL + 1
      IF (.NOT. LOPEN) THEN
        CALL VGETOUTDIR(OUTDIR, LENOUT)
        OPEN(UNIT=IU, FILE=OUTDIR(1:LENOUT)//'/vuint_diag.txt',
     *       STATUS='UNKNOWN')
        LOPEN = .TRUE.
        WRITE(IU,'(A)') '# HDR call nblock nnodstate nnodslv '//
     *   'nnodmst ndir nstates nprops jflags(1:2) rdata(1:4) surfint'
        WRITE(IU,'(A)') '# PT call k slvuid mstuid(1..n) pen '//
     *   'stiffdef area s1in s2in st1in st2in xs ys zs xm ym zm '//
     *   'n1 n2 n3'
      END IF
      LOUT = 0
      IF (NCALL .LE. 80 .OR. MOD(NCALL, 200) .EQ. 0) LOUT = 1
      IF (LOUT .EQ. 1) THEN
        WRITE(IU,'(A,8I8,2I10,4ES13.5,1X,A)') 'HDR ', NCALL, NBLOCK,
     *    NNODSTATE, NNODSLV, NNODMST, NDIR, NSTATES, NPROPS,
     *    JFLAGS(1), JFLAGS(2), RDATA(1), RDATA(2), RDATA(3),
     *    RDATA(4), TRIM(SURFINT)
      END IF
      DMIN = 1.0D30
      DMAX = -1.0D30
      SMAX = 0.0D0
C
C     -----------------------------------------------------------------
C     LOOP OVER BLOCK OF CONTACT PROXIMITY POINTS
C     -----------------------------------------------------------------
      DO K = 1, NBLOCK
C
C       Resolve penalty stiffness from PROPS(1) or Abaqus STIFFDEF
        IF (NPROPS .GE. 1 .AND. PROPS(1) .GT. 0.0D0) THEN
          KPEN = PROPS(1)
        ELSE IF (STIFFDEF(K) .GT. 0.0D0) THEN
          KPEN = STIFFDEF(K)
        ELSE
          KPEN = 1.0D11
        END IF
C
C       Resolve friction coefficient from PROPS(2)
        IF (NPROPS .GE. 2) THEN
          FRIC = PROPS(2)
        ELSE
          FRIC = 0.01D0
        END IF
C
C       Current kinematic penetration (positive = overclosure)
        D = PENETRATION(K)
        DMIN = MIN(DMIN, D)
        DMAX = MAX(DMAX, D)
        S1IN = STRESS(1, K)
        ST1IN = STATE(1, 1, K)
        ST2IN = STATE(2, 1, K)
        IF (LOUT .EQ. 1 .AND. NPRT .LT. 200000) THEN
          NPRT = NPRT + 1
          WRITE(IU,'(A,2I8,I10,4I10,16ES13.5)') 'PT ', NCALL, K,
     *      JSLVUID(1,K), (JMSTUID(J,K), J=1,MIN(NNODMST,4)),
     *      (0, J=MIN(NNODMST,4)+1,4),
     *      D, STIFFDEF(K), AREAPROX(K), S1IN, STRESS(2,K),
     *      ST1IN, ST2IN, COORDSLV(1,1,K), COORDSLV(2,1,K),
     *      COORDSLV(3,1,K), COORDMST(1,K), COORDMST(2,K),
     *      COORDMST(3,K), DIRCOS(1,1,K), DIRCOS(2,1,K),
     *      DIRCOS(3,1,K)
        END IF
        D_POS = MAX(D, 0.0D0)
C
C       Evaluate or initialize baseline offset d0
        IF (STATE(2, 1, K) .LT. 0.5D0) THEN
C         First time proximity point is active: store initial overlap
          D0 = D_POS
          STATE(1, 1, K) = D0
          STATE(2, 1, K) = 1.0D0
        ELSE
C         Subsequent evaluation: baseline only ratchets DOWNWARD
          D0 = STATE(1, 1, K)
          D0 = MIN(D0, D_POS)
          STATE(1, 1, K) = D0
        END IF
C
C       Penetration exceeding baseline generates normal penalty pressure
        D_EFF = MAX(0.0D0, D - D0)
        PRESS = KPEN * D_EFF
        STRESS(1, K) = PRESS
        SMAX = MAX(SMAX, PRESS)
C
C       Tangential Coulomb friction law
        IF (FRIC .GT. 0.0D0 .AND. PRESS .GT. 0.0D0) THEN
          DS1 = DRDISP(2, K)
          DS2 = 0.0D0
          IF (NDIR .GE. 3) DS2 = DRDISP(3, K)
C
          KS = KPEN
          TAU1 = STRESS(2, K) - KS * DS1
          TAU2 = 0.0D0
          IF (NDIR .GE. 3) TAU2 = STRESS(3, K) - KS * DS2
C
          TAU_MAG = SQRT(TAU1*TAU1 + TAU2*TAU2)
          TAU_CRIT = FRIC * PRESS
C
          IF (TAU_MAG .GT. TAU_CRIT .AND. TAU_MAG .GT. 1.0D-14) THEN
            SCALE = TAU_CRIT / TAU_MAG
            STRESS(2, K) = TAU1 * SCALE
            IF (NDIR .GE. 3) STRESS(3, K) = TAU2 * SCALE
          ELSE
            STRESS(2, K) = TAU1
            IF (NDIR .GE. 3) STRESS(3, K) = TAU2
          END IF
        ELSE
          DO IDIR = 2, NDIR
            STRESS(IDIR, K) = 0.0D0
          END DO
        END IF
C
C       Energy densities and thermal variables
        SED(K) = 0.5D0 * PRESS * D_EFF
        SFD(K) = 0.0D0
        SCD(K) = 0.0D0
        SPD(K) = 0.0D0
        SVD(K) = 0.0D0
        FLUXSLV(K) = 0.0D0
        FLUXMST(K) = 0.0D0
      END DO
      IF (LOUT .EQ. 1) THEN
        WRITE(IU,'(A,I8,3ES13.5)') 'SUM ', NCALL, DMIN, DMAX, SMAX
        CALL FLUSH(IU)
      END IF
C
      RETURN
      END
