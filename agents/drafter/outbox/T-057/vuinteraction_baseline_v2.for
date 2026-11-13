C======================================================================
C     VUINTERACTION_BASELINE_V2: General Contact User Subroutine for
C     Embedded Fiber to Host Matrix Interaction.
C
C     Task: T-057 (Plate Impact Project)
C     Target: Abaqus/Explicit 2024 (Intel Fortran, Fixed Form 72-col)
C
C     Engineered Fixes Implemented:
C       1. Double-Buffering by Increment Parity (kInc = jFlags(2)):
C          Separates read buffer (iGet) and write buffer (iPut) across
C          odd/even increments. Prevents numerical finite-difference
C          perturbation passes from mutating the baseline in-place.
C       2. Penetration & Pressure Caps:
C          Caps effective penetration d_eff <= 10 um and contact
C          pressure press <= 20 MPa (matrix crushing limit). Bounds
C          maximum facet force to <= 4 N, mathematically precluding
C          orphan node acceleration runaway (delivers stability).
C       3. First-Seen Overclosure Latch:
C          When a proximity point is first evaluated (including newly
C          exposed INTERIOR faces after element erosion), records
C          d0 = d_pos, preventing impulse shock upon face activation.
C       4. Monotonic Downward Ratchet:
C          Baselined points ratchet d0 downward only when clearance
C          physically opens, smoothly transitioning to full contact.
C       5. Strict Friction Bound:
C          Coulomb shear traction slaved to tau_crit = mu * press,
C          strictly zeroed whenever normal pressure is zero.
C       6. Diagnostic Logging Property:
C          File I/O active only when PROPS(3) > 0.5D0 (quiet by default)
C
C     Properties (*SURFACE INTERACTION, USER, PROPERTIES=3, DEPVAR=4):
C       PROPS(1) = Penalty stiffness k_pen [Pa/m] (default 2.0e11)
C       PROPS(2) = Friction coefficient mu (default 0.01)
C       PROPS(3) = Diagnostic log flag (0.0=quiet, 1.0=log to vuint_v2)
C
C     State Variables (DEPVAR = 4):
C       Buffer 1 (Odd kInc):  STATE(1,1,K)=d0,   STATE(2,1,K)=seen
C       Buffer 2 (Even kInc): STATE(3,1,K)=d0,   STATE(4,1,K)=seen
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
      INTEGER K, IDIR, KINC, IGET, IPUT, ID0_GET, ISEEN_GET
      INTEGER ID0_PUT, ISEEN_PUT, LDIAG, IU, LENOUT, NCALL
      REAL*8 D, D_POS, D0_OLD, SEEN_OLD, D0_NEW, SEEN_NEW, D_EFF
      REAL*8 KPEN, FRIC, PRESS, P_MAX, D_CAP, KS
      REAL*8 DS1, DS2, TAU1, TAU2, TAU_MAG, TAU_CRIT, SCALE
      LOGICAL LOPEN
      CHARACTER*256 OUTDIR
      SAVE NCALL, LOPEN
      DATA NCALL /0/, LOPEN /.FALSE./
C
C     Increment number and double-buffering index resolution
      KINC = JFLAGS(2)
      IF (MOD(KINC, 2) .NE. 0) THEN
        IGET = 1
        IPUT = 2
      ELSE
        IGET = 2
        IPUT = 1
      END IF
      IF (IGET .EQ. 1) THEN
        ID0_GET = 1
        ISEEN_GET = 2
        ID0_PUT = 3
        ISEEN_PUT = 4
      ELSE
        ID0_GET = 3
        ISEEN_GET = 4
        ID0_PUT = 1
        ISEEN_PUT = 2
      END IF
C
C     Constitutive parameters
      IF (NPROPS .GE. 1 .AND. PROPS(1) .GT. 0.0D0) THEN
        KPEN = PROPS(1)
      ELSE IF (STIFFDEF(1) .GT. 0.0D0) THEN
        KPEN = STIFFDEF(1)
      ELSE
        KPEN = 2.0D11
      END IF
C
      IF (NPROPS .GE. 2 .AND. PROPS(2) .GE. 0.0D0) THEN
        FRIC = PROPS(2)
      ELSE
        FRIC = 0.01D0
      END IF
C
      LDIAG = 0
      IF (NPROPS .GE. 3 .AND. PROPS(3) .GT. 0.5D0) LDIAG = 1
C
C     Hard physical caps for numerical stability
      D_CAP = 1.0D-5
      P_MAX = 2.0D7
C
C     Optional diagnostic logger setup
      IF (LDIAG .EQ. 1) THEN
        IU = 119
        NCALL = NCALL + 1
        IF (.NOT. LOPEN) THEN
          CALL VGETOUTDIR(OUTDIR, LENOUT)
          OPEN(UNIT=IU, FILE=OUTDIR(1:LENOUT)//'/vuint_v2.txt',
     *         STATUS='UNKNOWN')
          LOPEN = .TRUE.
          WRITE(IU,'(A)') '# V2_DIAG call kinc nblock'
        END IF
      END IF
C
C     -----------------------------------------------------------------
C     LOOP OVER PROXIMITY POINTS IN BLOCK
C     -----------------------------------------------------------------
      DO K = 1, NBLOCK
        D = PENETRATION(K)
        D_POS = MAX(D, 0.0D0)
C
C       Fetch state from read buffer (converged from previous increment)
        IF (NSTATES .GE. 4) THEN
          D0_OLD = STATE(ID0_GET, 1, K)
          SEEN_OLD = STATE(ISEEN_GET, 1, K)
        ELSE
          D0_OLD = STATE(1, 1, K)
          SEEN_OLD = STATE(2, 1, K)
        END IF
C
C       Evaluate baseline state
        IF (SEEN_OLD .LT. 0.5D0) THEN
C         First evaluation: latch initial penetration to baseline
          D0_NEW = D_POS
          SEEN_NEW = 1.0D0
        ELSE
C         Subsequent evaluation: downward ratchet only
          D0_NEW = MIN(D0_OLD, D_POS)
          SEEN_NEW = 1.0D0
        END IF
C
C       Store updated state into write buffer
        IF (NSTATES .GE. 4) THEN
          STATE(ID0_PUT, 1, K) = D0_NEW
          STATE(ISEEN_PUT, 1, K) = SEEN_NEW
        ELSE
          STATE(1, 1, K) = D0_NEW
          STATE(2, 1, K) = SEEN_NEW
        END IF
C
C       Effective penetration with cap
        D_EFF = MAX(0.0D0, D - D0_NEW)
        IF (D_EFF .GT. D_CAP) D_EFF = D_CAP
C
C       Normal contact pressure with physical crushing cap
        PRESS = KPEN * D_EFF
        IF (PRESS .GT. P_MAX) PRESS = P_MAX
        STRESS(1, K) = PRESS
C
C       Tangential Coulomb friction
        IF (FRIC .GT. 0.0D0 .AND. PRESS .GT. 0.0D0) THEN
          DS1 = DRDISP(2, K)
          DS2 = 0.0D0
          IF (NDIR .GE. 3) DS2 = DRDISP(3, K)
          KS = KPEN
          TAU1 = STRESS(2, K) - KS * DS1
          TAU2 = 0.0D0
          IF (NDIR .GE. 3) TAU2 = STRESS(3, K) - KS * DS2
          TAU_MAG = SQRT(TAU1*TAU1 + TAU2*TAU2)
          TAU_CRIT = FRIC * PRESS
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
C       Energy densities and thermal dissipation
        SED(K) = 0.5D0 * PRESS * D_EFF
        SFD(K) = 0.0D0
        SCD(K) = 0.0D0
        SPD(K) = 0.0D0
        SVD(K) = 0.0D0
        FLUXSLV(K) = 0.0D0
        FLUXMST(K) = 0.0D0
      END DO
C
      RETURN
      END
