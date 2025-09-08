class TimingContextRaceConditionError(RuntimeError):
    """
    Error raised when AIModel.timing_context is started in multi-threaded environment.
    """

    pass
