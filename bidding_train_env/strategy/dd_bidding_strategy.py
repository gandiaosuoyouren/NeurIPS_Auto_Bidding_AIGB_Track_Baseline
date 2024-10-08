import numpy as np
import torch
from bidding_train_env.strategy.base_bidding_strategy import BaseBiddingStrategy
import numpy as np
from bidding_train_env.baseline.dd.DFUSER import DFUSER
import os


class DdBiddingStrategy(BaseBiddingStrategy):
    """
    Decision-Diffuser-PlayerStrategy
    """

    def __init__(self, i, base_model_path = '', budget=100, name="Decision-Diffuser-PlayerStrategy", cpa=2, category=1):
        super().__init__(budget, name, cpa, category)
        model_path = os.path.join('/home/disk2/auto-bidding/models/diffuser_temp_haorui.pt')
        # model_path = os.path.join('/home/disk2/auto-bidding/models', f'diffuser_{i}.pt')
        # 如果传入模拟agent模型路径，则修改路径
        if base_model_path != '':
            model_path = base_model_path
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.model = DFUSER().eval()
        self.model.load_net(model_path, device=self.device)
        self.state_dim = 22
        self.input = np.zeros((48, self.state_dim + 1))

    def reset(self):
        self.remaining_budget = self.budget
        self.input = np.zeros((48, self.state_dim + 1))

    def bidding(self, timeStepIndex, pValues, pValueSigmas, historyPValueInfo, historyBid,
                historyAuctionResult, historyImpressionResult, historyLeastWinningCost):
        """
        Bids for all the opportunities in a delivery period

        parameters:
         @timeStepIndex: the index of the current decision time step.
         @pValues: the conversion action probability.
         @pValueSigmas: the prediction probability uncertainty.
         @historyPValueInfo: the history predicted value and uncertainty for each opportunity.
         @historyBid: the advertiser's history bids for each opportunity.
         @historyAuctionResult: the history auction results for each opportunity.
         @historyImpressionResult: the history impression result for each opportunity.
         @historyLeastWinningCosts: the history least wining costs for each opportunity.

        return:
            Return the bids for all the opportunities in the delivery period.
        """
        time_left = (48 - timeStepIndex) / 48
        budget_left = self.remaining_budget / self.budget if self.budget > 0 else 0
        history_xi = [result[:, 0] for result in historyAuctionResult]
        history_slot = [result[:, 1] for result in historyAuctionResult]
        history_pValue = [result[:, 0] for result in historyPValueInfo]
        history_exposure = [result[:, 0] for result in historyImpressionResult]
        history_conversion = [result[:, 1] for result in historyImpressionResult]

        historical_xi_mean = np.mean([np.mean(xi) for xi in history_xi]) if history_xi else 0

        historical_conversion_mean = np.mean(
            [np.mean(reward) for reward in history_conversion]) if history_conversion else 0

        slot_1_win = 1e-10
        slot_2_win = 1e-10
        slot_3_win = 1e-10
        slot_1_exposure = 0
        slot_2_exposure = 0
        slot_3_exposure = 0
        slot_1_win_least_alpha = 1
        slot_2_win_least_alpha = 1
        slot_3_win_least_alpha = 1
        for timeStepIndex in range(0, len(historyAuctionResult)):
            for pvindex in range(0, len(historyAuctionResult[timeStepIndex])):
                # winning
                if history_xi[timeStepIndex][pvindex] == 1:
                    # slot
                    if history_slot[timeStepIndex][pvindex] == 1:
                        slot_1_win += 1
                        alpha = historyBid[timeStepIndex][pvindex] / history_pValue[timeStepIndex][pvindex]
                        slot_1_win_least_alpha = min(slot_1_win_least_alpha, alpha)
                        # exposed
                        if history_exposure[timeStepIndex][pvindex] == 1:
                            slot_1_exposure += 1
                    if history_slot[timeStepIndex][pvindex] == 2:
                        slot_2_win += 1
                        alpha = historyBid[timeStepIndex][pvindex] / history_pValue[timeStepIndex][pvindex]
                        slot_2_win_least_alpha = min(slot_2_win_least_alpha, alpha)
                        # exposed
                        if history_exposure[timeStepIndex][pvindex] == 1:
                            slot_3_exposure += 1
                    if history_slot[timeStepIndex][pvindex] == 3:
                        slot_3_win += 1
                        alpha = historyBid[timeStepIndex][pvindex] / history_pValue[timeStepIndex][pvindex]
                        slot_3_win_least_alpha = min(slot_3_win_least_alpha, alpha)
                        # exposed
                        if history_exposure[timeStepIndex][pvindex] == 1:
                            slot_3_exposure += 1
        historical_slot_1_exposure_rate = slot_1_exposure / slot_1_win
        historical_slot_2_exposure_rate = slot_2_exposure / slot_2_win
        historical_slot_3_exposure_rate = slot_3_exposure / slot_3_win

        historical_LeastWinningCost_mean = np.mean(
            [np.mean(price) for price in historyLeastWinningCost]) if historyLeastWinningCost else 0

        historical_pValues_mean = np.mean([np.mean(value) for value in history_pValue]) if history_pValue else 0

        historical_bid_mean = np.mean([np.mean(bid) for bid in historyBid]) if historyBid else 0

        def mean_of_last_n_elements(history, n):
            last_three_data = history[max(0, n - 3):n]
            if len(last_three_data) == 0:
                return 0
            else:
                return np.mean([np.mean(data) for data in last_three_data])

        last_three_xi_mean = mean_of_last_n_elements(history_xi, 3)
        last_three_conversion_mean = mean_of_last_n_elements(history_conversion, 3)
        last_three_LeastWinningCost_mean = mean_of_last_n_elements(historyLeastWinningCost, 3)
        last_three_pValues_mean = mean_of_last_n_elements(history_pValue, 3)
        last_three_bid_mean = mean_of_last_n_elements(historyBid, 3)

        current_pValues_mean = np.mean(pValues)
        current_pv_num = len(pValues)

        historical_pv_num_total = sum(len(bids) for bids in historyBid) if historyBid else 0
        last_three_ticks = slice(max(0, timeStepIndex - 3), timeStepIndex)
        last_three_pv_num_total = sum(
            [len(historyBid[i]) for i in range(max(0, timeStepIndex - 3), timeStepIndex)]) if historyBid else 0

        test_state = np.array([
            time_left, budget_left, historical_bid_mean, last_three_bid_mean,
            historical_LeastWinningCost_mean, historical_pValues_mean, historical_conversion_mean,
            historical_xi_mean, last_three_LeastWinningCost_mean, last_three_pValues_mean,
            last_three_conversion_mean, last_three_xi_mean,
            current_pValues_mean, current_pv_num, last_three_pv_num_total,
            historical_pv_num_total, historical_slot_1_exposure_rate, historical_slot_2_exposure_rate, historical_slot_3_exposure_rate,
            slot_1_win_least_alpha, slot_2_win_least_alpha, slot_3_win_least_alpha
        ])

        for i in range(self.state_dim):
            self.input[timeStepIndex, i] = test_state[i]
        self.input[:, -1] = timeStepIndex
        x = torch.tensor(self.input.reshape(-1), device=self.device)
        cpa_tensor = torch.tensor([[[self.cpa]]], device=self.device, dtype=torch.float32)
        alpha = self.model(x, cpa_tensor)
        alpha = alpha.item()
        alpha = max(0, alpha)
        # alpha = 0.2 * alpha + 0.8 * self.cpa
        bids = alpha * pValues

        return bids
