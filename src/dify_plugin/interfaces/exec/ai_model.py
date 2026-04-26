class TimingContextRaceConditionError(RuntimeError):
    """Error raised when AIModel.timing_context starts in multiple threads."""
