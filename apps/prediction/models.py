from django.db import models


class ElectionHistory(models.Model):
    # Core identifiers
    year                  = models.IntegerField()
    assembly_no           = models.IntegerField(null=True, blank=True)
    constituency_no       = models.IntegerField(null=True, blank=True)
    constituency          = models.CharField(max_length=150)
    constituency_type     = models.CharField(max_length=50, blank=True)   # GEN/SC/ST
    district              = models.CharField(max_length=100, blank=True)
    state                 = models.CharField(max_length=100, default='Gujarat')
    sub_region            = models.CharField(max_length=100, blank=True)

    # Candidate info
    candidate             = models.CharField(max_length=200)
    sex                   = models.CharField(max_length=10, blank=True)
    age                   = models.IntegerField(null=True, blank=True)
    candidate_type        = models.CharField(max_length=50, blank=True)   # CONTESTANT / etc
    education             = models.CharField(max_length=100, blank=True)
    profession_main       = models.CharField(max_length=100, blank=True)
    profession_second     = models.CharField(max_length=100, blank=True)

    # Party info
    party                 = models.CharField(max_length=100)
    party_id              = models.CharField(max_length=50, blank=True)
    party_type            = models.CharField(max_length=50, blank=True)   # INC/NEC/OTH

    # Vote data
    votes                 = models.IntegerField(default=0)
    valid_votes           = models.IntegerField(default=0)
    electors              = models.IntegerField(default=0)
    vote_share            = models.FloatField(default=0.0)
    voter_turnout         = models.FloatField(default=0.0)
    position              = models.IntegerField(null=True, blank=True)    # 1 = winner
    won                   = models.BooleanField(default=False)
    deposit_lost          = models.BooleanField(default=False)

    # Contest info
    n_candidates          = models.IntegerField(null=True, blank=True)    # N_Cand
    margin                = models.IntegerField(null=True, blank=True)
    margin_pct            = models.FloatField(null=True, blank=True)
    enop                  = models.FloatField(null=True, blank=True)      # Eff. no. of parties

    # Incumbent / history
    incumbent             = models.IntegerField(default=0)                # 1/0
    recontest             = models.IntegerField(default=0)
    turncoat              = models.IntegerField(default=0)
    no_terms              = models.IntegerField(null=True, blank=True)
    same_constituency     = models.IntegerField(null=True, blank=True)
    same_party            = models.IntegerField(null=True, blank=True)
    last_party            = models.CharField(max_length=100, blank=True)
    last_constituency     = models.CharField(max_length=150, blank=True)
    last_poll             = models.IntegerField(null=True, blank=True)
    contested             = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-year', 'constituency', 'position']
        unique_together = ('year', 'constituency_no', 'candidate', 'party')

    def __str__(self):
        return f"{self.year} | {self.constituency} | {self.party} | {self.candidate}"


class PredictionResult(models.Model):
    constituency          = models.CharField(max_length=150)
    predicted_party       = models.CharField(max_length=100)
    confidence            = models.FloatField()
    predicted_vote_share  = models.FloatField()
    predicted_turnout     = models.FloatField()
    created_at            = models.DateTimeField(auto_now_add=True)
    model_version         = models.CharField(max_length=50, default='v2')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.constituency} → {self.predicted_party} ({self.confidence:.1%})"