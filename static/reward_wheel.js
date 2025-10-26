// Reward Wheel Functionality
class RewardWheel {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.sections = options.sections || 8;
        this.colors = options.colors || [
            '#ff6384', '#36a2eb', '#ffce56', '#4bc0c0',
            '#9966ff', '#ff9f40', '#ff6384', '#36a2eb'
        ];
        this.rewards = options.rewards || [
            'Free Homework Pass',
            'Lunch with Teacher',
            'Extra Computer Time',
            'Front Line Pass',
            'School Merch',
            'Special Recognition',
            'Gift Card',
            'Pizza Party'
        ];
        this.isSpinning = false;
        this.init();
    }

    init() {
        this.createWheel();
        this.addEventListeners();
    }

    createWheel() {
        this.container.innerHTML = '';
        this.container.className = 'reward-wheel';
        
        const wheelSections = document.createElement('div');
        wheelSections.className = 'wheel-sections';
        
        for (let i = 0; i < this.sections; i++) {
            const section = document.createElement('div');
            section.className = 'wheel-section';
            section.style.setProperty('--i', i);
            section.style.setProperty('--clr', this.colors[i]);
            section.textContent = this.rewards[i];
            wheelSections.appendChild(section);
        }
        
        this.container.appendChild(wheelSections);
        
        // Add pointer
        const pointer = document.createElement('div');
        pointer.className = 'wheel-pointer';
        this.container.appendChild(pointer);
    }

    addEventListeners() {
        const spinBtn = document.getElementById('spinWheelBtn');
        if (spinBtn) {
            spinBtn.addEventListener('click', () => this.spin());
        }
    }

    spin() {
        if (this.isSpinning) return;
        
        this.isSpinning = true;
        const spinBtn = document.getElementById('spinWheelBtn');
        if (spinBtn) spinBtn.disabled = true;

        // Call the spin API to determine the result
        fetch('/api/spin', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'error') {
                throw new Error(data.message);
            }

            // Calculate rotation based on landed section
            const section = data.section; // 0-7 from the server
            const baseRotation = section * (360 / this.sections); // Which section
            
            // Add 5 full rotations plus the angle to the section
            const degrees = (5 * 360) + baseRotation;
            
            this.container.style.transform = `rotate(${degrees}deg)`;
            this.container.style.transition = 'transform 3s cubic-bezier(0.2, 0.8, 0.3, 1)';

            setTimeout(() => {
                this.displayResult(data.reward);
                this.isSpinning = false;
                if (spinBtn) spinBtn.disabled = false;
                
                // Update points display
                const pointsDisplay = document.getElementById('userPoints');
                if (pointsDisplay) {
                    pointsDisplay.innerHTML = `🪙 ${data.points} points`;
                }

                // Update recent winners
                this.updateRecentWinners();
            }, 3000);
        })
        .catch(error => {
            this.isSpinning = false;
            if (spinBtn) spinBtn.disabled = false;
            alert(error.message || 'Failed to spin the wheel. Try again.');
        });
    }

    calculateResult(degrees) {
        const normalizedDegrees = degrees % 360;
        const segmentSize = 360 / this.sections;
        const rewardIndex = Math.floor(normalizedDegrees / segmentSize);
        return this.rewards[rewardIndex];
    }

    displayResult(reward) {
        const resultDiv = document.getElementById('spinResult');
        if (resultDiv) {
            resultDiv.innerHTML = `
                <div class="reward-result" style="
                    background: linear-gradient(135deg, var(--yellow), #ff9800);
                    color: var(--black);
                    padding: 20px;
                    border-radius: 10px;
                    text-align: center;
                    margin: 20px 0;
                    animation: pulse 1s infinite;
                ">
                    <h3>🎉 Congratulations! 🎉</h3>
                    <p style="font-size: 1.2rem; margin: 10px 0;">
                        You won: <strong>${reward}</strong>
                    </p>
                    <small>Your reward has been added to your account</small>
                </div>
            `;
        }

        // Save reward via API
        this.saveReward(reward);
    }

    saveReward(reward) {
        // Call the spin API endpoint
        fetch('/api/spin', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            console.log('Reward saved:', data);
        })
        .catch(error => {
            console.error('Error saving reward:', error);
        });
    }
}

// Update recent winners list
    updateRecentWinners() ;
        RewardManager.getRecentWinners()
            .then(data => {
                if (data.status === 'success') {
                    const winnersDiv = document.getElementById('recentWinners');
                    if (winnersDiv) {
                        if (data.winners.length === 0) {
                            winnersDiv.innerHTML = '<p>No rewards claimed yet. Be the first winner!</p>';
                            return;
                        }
                        const html = data.winners.map(winner => `
                            <div class="recent-winner" style="
                                background: var(--black);
                                padding: 10px;
                                margin: 5px 0;
                                border-radius: 8px;
                                display: flex;
                                align-items: center;
                                gap: 10px;
                            ">
                                <div style="font-size: 1.2rem;">🏆</div>
                                <div>
                                    <strong>${winner.username}</strong> won
                                    <span style="color: var(--yellow);">${winner.reward}</span>
                                    <br>
                                    <small>${winner.awarded_at}</small>
                                </div>
                            </div>
                        `).join('');
                        winnersDiv.innerHTML = html;
                    }
                }
            });
    }

// Initialize wheel when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const wheel = new RewardWheel('rewardWheel', {
        sections: 8,
        rewards: [
            'Free Homework Pass',
            'Lunch with Favorite Teacher',
            'Extra Computer Time (30 mins)',
            'Front of Lunch Line Pass',
            'School Merchandise Pack',
            'Special Recognition Certificate',
            '₵20 Gift Card',
            'Pizza Party for Your Class'
        ]
    });

    // Initialize points
    RewardManager.getPoints()
        .then(data => {
            if (data.status === 'success') {
                const pointsDisplay = document.getElementById('userPoints');
                if (pointsDisplay) {
                    pointsDisplay.innerHTML = `🪙 ${data.points} points`;
                }
            }
        });

    // Initialize recent winners
    wheel.updateRecentWinners();
});

// Utility functions for rewards
const RewardManager = {
    claimReward: function(rewardId) {
        return fetch(`/api/claim_reward/${rewardId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json());
    },

    getUserRewards: function() {
        return fetch('/api/user_rewards')
            .then(response => response.json());
    },

    getPoints: function() {
        return fetch('/api/points')
            .then(response => response.json());
    },
    
    getRecentWinners: function() {
        return fetch('/api/recent_winners')
            .then(response => response.json());
    }
};

// Export for global access
window.RewardWheel = RewardWheel;
window.RewardManager = RewardManager;